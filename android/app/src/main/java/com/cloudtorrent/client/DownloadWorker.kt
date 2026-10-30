package com.cloudtorrent.client

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.datastore.preferences.core.*
import androidx.documentfile.provider.DocumentFile
import androidx.room.*
import androidx.work.*
import java.io.FileOutputStream
import java.util.UUID
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import okhttp3.OkHttpClient
import okhttp3.Request

@Entity
data class Transfer(
    @PrimaryKey val id: String,
    val fileId: String,
    val uri: String,
    val size: Long,
    val offset: Long = 0,
    val state: String = "queued",
    val etag: String? = null,
    @ColumnInfo(defaultValue = "''") val name: String = "",
    @ColumnInfo(defaultValue = "0") val created: Double = 0.0,
)

@Dao
interface TransferDao {
    @Query("SELECT * FROM Transfer WHERE fileId=:fileId LIMIT 1")
    suspend fun forFile(fileId: String): Transfer?

    @Query("SELECT * FROM Transfer ORDER BY id")
    fun observe(): kotlinx.coroutines.flow.Flow<List<Transfer>>

    @Query("SELECT * FROM Transfer WHERE id=:id") suspend fun get(id: String): Transfer?

    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun put(t: Transfer)

    @Delete suspend fun delete(t: Transfer)
}

@Database(entities = [Transfer::class], version = 2, exportSchema = false)
abstract class Transfers : RoomDatabase() {
    abstract fun transfers(): TransferDao

    companion object {
        @Volatile private var instance: Transfers? = null

        fun get(c: Context): Transfers =
            instance
                ?: synchronized(this) {
                    instance
                        ?: Room.databaseBuilder(
                                c.applicationContext,
                                Transfers::class.java,
                                "transfers.db",
                            )
                            .addMigrations(
                                object : androidx.room.migration.Migration(1, 2) {
                                    override fun migrate(
                                        db: androidx.sqlite.db.SupportSQLiteDatabase
                                    ) {
                                        db.execSQL(
                                            "ALTER TABLE Transfer ADD COLUMN name TEXT NOT NULL DEFAULT ''"
                                        )
                                        db.execSQL(
                                            "ALTER TABLE Transfer ADD COLUMN created REAL NOT NULL DEFAULT 0"
                                        )
                                    }
                                }
                            )
                            .build()
                            .also { instance = it }
                }
    }
}

fun enqueueDownload(context: Context, f: CloudFile, vm: ClientViewModel) {
    vm.action { queueDownload(context, f) }
}

suspend fun queueDownload(context: Context, f: CloudFile): Unit =
    withContext(Dispatchers.IO) {
        if (Transfers.get(context).transfers().forFile(f.id) != null) return@withContext
        require(f.drive_id != null || (f.server_present && f.state == "uploading")) {
            "Файл ещё не готов"
        }
        val p = context.settings.data.first()
        val tree =
            p[stringPreferencesKey("folder")] ?: error("Выберите папку загрузок в настройках")
        val root =
            DocumentFile.fromTreeUri(context, Uri.parse(tree)) ?: error("Нет доступа к папке")
        val doc =
            root.createFile("application/octet-stream", f.path.substringAfterLast('/'))
                ?: error("Не удалось создать файл")
        val id = UUID.randomUUID().toString()
        Transfers.get(context)
            .transfers()
            .put(
                Transfer(
                    id,
                    f.id,
                    doc.uri.toString(),
                    f.size,
                    name = f.path.substringAfterLast('/'),
                    created = System.currentTimeMillis() / 1000.0,
                )
            )
        val constraints = phoneConstraints(p)
        val work =
            OneTimeWorkRequestBuilder<DownloadWorker>()
                .setConstraints(constraints)
                .setInputData(workDataOf("id" to id))
                .addTag("download-$id")
                .build()
        WorkManager.getInstance(context).enqueueUniqueWork(id, ExistingWorkPolicy.KEEP, work)
        Unit
    }

class DownloadWorker(context: Context, params: WorkerParameters) :
    CoroutineWorker(context, params) {
    private fun foreground(done: Long, total: Long): ForegroundInfo {
        val manager = applicationContext.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel("transfers", "Загрузка файлов", NotificationManager.IMPORTANCE_LOW)
        )
        val cancel = WorkManager.getInstance(applicationContext).createCancelPendingIntent(id)
        val notification =
            NotificationCompat.Builder(applicationContext, "transfers")
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setContentTitle("Cloud Torrent Client")
                .setContentText("${bytes(done)} / ${bytes(total)}")
                .setProgress(100, if (total > 0) (100.0 * done / total).toInt() else 0, false)
                .setOngoing(true)
                .addAction(android.R.drawable.ic_media_pause, "Пауза", cancel)
                .build()
        return ForegroundInfo(
            id.hashCode(),
            notification,
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
        )
    }

    override suspend fun doWork(): Result =
        withContext(Dispatchers.IO) {
            val dao = Transfers.get(applicationContext).transfers()
            val tid = inputData.getString("id") ?: return@withContext Result.failure()
            var row = dao.get(tid) ?: return@withContext Result.failure()
            if (row.state == "ready") return@withContext Result.success()
            try {
                setForeground(foreground(row.offset, row.size))
                val p = applicationContext.settings.data.first()
                val url = p[stringPreferencesKey("url")] ?: error("Нет backend")
                require(url.startsWith("https://"))
                val token = Vault(applicationContext).open(p[stringPreferencesKey("token")] ?: "")
                val request =
                    Request.Builder()
                        .url(url.trimEnd('/') + "/files/${row.fileId}/download")
                        .header("Authorization", "Bearer $token")
                        .apply {
                            if (row.offset > 0) {
                                header("Range", "bytes=${row.offset}-")
                                row.etag?.let { header("If-Range", it) }
                            }
                        }
                        .build()
                val connectivity =
                    applicationContext.getSystemService(android.net.ConnectivityManager::class.java)
                val wifiOnly = p[booleanPreferencesKey("wifi")] != false
                val active = connectivity.activeNetwork
                val activeIsVpn =
                    connectivity
                        .getNetworkCapabilities(active)
                        ?.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN) == true
                val chosen =
                    if (activeIsVpn) active
                    else if (android.os.Build.VERSION.SDK_INT >= 28) network ?: active else active
                if (wifiOnly)
                    require(
                        chosen != null &&
                            connectivity
                                .getNetworkCapabilities(chosen)
                                ?.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI) ==
                                true
                    ) {
                        "Для передачи требуется Wi-Fi"
                    }
                OkHttpClient.Builder()
                    .apply {
                        if (wifiOnly && chosen != null) {
                            socketFactory(chosen.socketFactory)
                            dns(
                                object : okhttp3.Dns {
                                    override fun lookup(hostname: String) =
                                        chosen.getAllByName(hostname).toList()
                                }
                            )
                        }
                    }
                    .readTimeout(120, java.util.concurrent.TimeUnit.SECONDS)
                    .build()
                    .newCall(request)
                    .execute()
                    .use { response ->
                        require(response.isSuccessful) { "HTTP ${response.code}" }
                        if (row.offset > 0 && response.code == 200) {
                            row = row.copy(offset = 0, etag = response.header("ETag"))
                            dao.put(row)
                        }
                        if (row.offset > 0) {
                            require(response.code == 206) { "Сервер не подтвердил докачку" }
                            require(
                                response
                                    .header("Content-Range")
                                    ?.startsWith("bytes ${row.offset}-") == true
                            ) {
                                "Неверный Content-Range"
                            }
                        }
                        val descriptor =
                            applicationContext.contentResolver.openFileDescriptor(
                                Uri.parse(row.uri),
                                "rw",
                            ) ?: error("Нет доступа SAF")
                        descriptor.use { fd ->
                            val stat = android.system.Os.fstatvfs(fd.fileDescriptor)
                            require(stat.f_bavail * stat.f_frsize >= row.size - row.offset) {
                                "Недостаточно памяти"
                            }
                            FileOutputStream(fd.fileDescriptor).use { out ->
                                out.channel.position(row.offset)
                                if (row.offset == 0L) out.channel.truncate(0)
                                val body = response.body ?: error("Нет тела ответа")
                                body.byteStream().use { input ->
                                    val buffer = ByteArray(256 * 1024)
                                    var committed = row.offset
                                    var last = System.currentTimeMillis()
                                    while (true) {
                                        ensureActive()
                                        if (isStopped) throw CancellationException()
                                        val started = System.nanoTime()
                                        val count = input.read(buffer)
                                        ensureActive()
                                        if (count < 0) break
                                        require(row.offset + count <= row.size) {
                                            "Размер ответа больше файла"
                                        }
                                        out.write(buffer, 0, count)
                                        row =
                                            row.copy(
                                                offset = row.offset + count,
                                                state = "downloading",
                                                etag = response.header("ETag"),
                                            )
                                        if (p[booleanPreferencesKey("speed_on")] == true) {
                                            val ms =
                                                count * 1000L /
                                                    ((p[intPreferencesKey("speed")] ?: 10) *
                                                        1024 *
                                                        1024) -
                                                    (System.nanoTime() - started) / 1000000
                                            if (ms > 0) delay(ms)
                                        }
                                        if (
                                            row.offset - committed >= 1024 * 1024 ||
                                                System.currentTimeMillis() - last > 1000
                                        ) {
                                            out.fd.sync()
                                            dao.put(row)
                                            committed = row.offset
                                            last = System.currentTimeMillis()
                                            setForeground(foreground(row.offset, row.size))
                                            setProgress(workDataOf("bytes" to row.offset))
                                        }
                                    }
                                    out.fd.sync()
                                    dao.put(row)
                                }
                            }
                        }
                    }
                require(row.offset == row.size) { "Неполный ответ" }
                dao.put(row.copy(state = "ready"))
                Result.success()
            } catch (e: CancellationException) {
                withContext(NonCancellable) {
                    val saved = dao.get(tid)
                    if (saved != null) dao.put(saved.copy(state = "paused"))
                }
                throw e
            } catch (e: Exception) {
                dao.put((dao.get(tid) ?: row).copy(state = "error"))
                if (runAttemptCount < 4) Result.retry()
                else Result.failure(workDataOf("error" to (e.message ?: "Ошибка передачи")))
            }
        }
}

fun resumeDownload(context: Context, id: String, vm: ClientViewModel) {
    vm.action {
        val p = context.settings.data.first()
        val dao = Transfers.get(context).transfers()
        val row = dao.get(id) ?: return@action
        val writable =
            try {
                DocumentFile.fromSingleUri(context, Uri.parse(row.uri))?.canWrite() == true
            } catch (_: Exception) {
                false
            }
        if (!writable) {
            val tree = p[stringPreferencesKey("folder")] ?: error("Выберите папку загрузок заново")
            val directory =
                DocumentFile.fromTreeUri(context, Uri.parse(tree)) ?: error("Нет доступа к папке")
            val target =
                directory.createFile("application/octet-stream", row.name.ifEmpty { "download" })
                    ?: error("Выберите доступную папку загрузок")
            dao.put(
                row.copy(uri = target.uri.toString(), offset = 0, etag = null, state = "queued")
            )
        }
        val constraints = phoneConstraints(p)
        val work =
            OneTimeWorkRequestBuilder<DownloadWorker>()
                .setConstraints(constraints)
                .setInputData(workDataOf("id" to id))
                .addTag("download-$id")
                .build()
        WorkManager.getInstance(context).enqueueUniqueWork(id, ExistingWorkPolicy.REPLACE, work)
    }
}

class DiscoveryWorker(context: Context, parameters: WorkerParameters) :
    CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result =
        withContext(Dispatchers.IO) {
            val p = applicationContext.settings.data.first()
            if (
                p[booleanPreferencesKey("auto_phone")] == false ||
                    p[stringPreferencesKey("url")] == null ||
                    p[stringPreferencesKey("folder")] == null
            )
                return@withContext Result.success()
            try {
                val api = Repository(Vault(applicationContext)).api()
                if (!api.limits().phone_downloads) return@withContext Result.success()
                for (file in api.files().filter { it.drive_id != null }) queueDownload(
                    applicationContext,
                    file,
                )
                Result.success()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Result.retry()
            }
        }
}

suspend fun refreshTransferConstraints(context: Context) {
    val p = context.settings.data.first()
    for (t in
        Transfers.get(context).transfers().observe().first().filter {
            it.state in listOf("queued", "downloading")
        }) {
        val c = phoneConstraints(p)
        val w =
            OneTimeWorkRequestBuilder<DownloadWorker>()
                .setConstraints(c)
                .setInputData(workDataOf("id" to t.id))
                .addTag("download-${t.id}")
                .build()
        WorkManager.getInstance(context).enqueueUniqueWork(t.id, ExistingWorkPolicy.REPLACE, w)
    }
}

fun phoneConstraints(p: androidx.datastore.preferences.core.Preferences): Constraints {
    val builder =
        Constraints.Builder().setRequiresCharging(p[booleanPreferencesKey("charging")] == true)
    if (p[booleanPreferencesKey("wifi")] != false) {
        val request =
            android.net.NetworkRequest.Builder()
                .addTransportType(android.net.NetworkCapabilities.TRANSPORT_WIFI)
                .addCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .removeCapability(android.net.NetworkCapabilities.NET_CAPABILITY_NOT_VPN)
                .build()
        builder.setRequiredNetworkRequest(request, NetworkType.UNMETERED)
    } else builder.setRequiredNetworkType(NetworkType.CONNECTED)
    return builder.build()
}
