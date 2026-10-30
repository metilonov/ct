package com.cloudtorrent.client

import android.app.Application
import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.datastore.preferences.core.*
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.HiltAndroidApp
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import java.security.KeyStore
import java.util.concurrent.TimeUnit
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*

@HiltAndroidApp
class ClientApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        androidx.work.WorkManager.getInstance(this)
            .enqueueUniquePeriodicWork(
                "server-file-discovery",
                androidx.work.ExistingPeriodicWorkPolicy.KEEP,
                androidx.work
                    .PeriodicWorkRequestBuilder<DiscoveryWorker>(
                        15,
                        java.util.concurrent.TimeUnit.MINUTES,
                    )
                    .setConstraints(
                        androidx.work.Constraints.Builder()
                            .setRequiredNetworkType(androidx.work.NetworkType.CONNECTED)
                            .build()
                    )
                    .build(),
            )
    }
}

val Context.settings by preferencesDataStore("settings")

class Vault @Inject constructor(@ApplicationContext val context: Context) {
    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        return (ks.getKey("api", null) as? SecretKey)
            ?: KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
                .apply {
                    init(
                        KeyGenParameterSpec.Builder(
                                "api",
                                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                            )
                            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                            .build()
                    )
                }
                .generateKey()
    }

    fun seal(s: String): String {
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.ENCRYPT_MODE, key())
        return Base64.encodeToString(c.iv + c.doFinal(s.toByteArray()), Base64.NO_WRAP)
    }

    fun open(s: String): String {
        if (s.isEmpty()) return ""
        val b = Base64.decode(s, Base64.NO_WRAP)
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, b.copyOfRange(0, 12)))
        return String(c.doFinal(b.copyOfRange(12, b.size)))
    }
}

data class Torrent(
    val id: String,
    val name: String,
    val state: String,
    val total_bytes: Long,
    val progress: Double,
    val speed: Long,
    val error: String?,
    val phase_progress: Double? = null,
    val phase_completed_bytes: Long? = null,
    val phase_total_bytes: Long? = null,
    val phase_file: String? = null,
    val eta_seconds: Long? = null,
)

data class CloudFile(
    val id: String,
    val task_id: String,
    val path: String,
    val size: Long,
    val state: String,
    val drive_id: String?,
    val created: Double = 0.0,
    val server_present: Boolean = false,
)

data class Storage(
    val capacity_bytes: Long = 0,
    val used_bytes: Long = 0,
    val free_bytes: Long = 0,
)

data class Automation(
    val auto_drive: Boolean = true,
    val auto_delete: Boolean = true,
    val parallelism: Int = 1,
)

data class Server(val connected: Boolean = false, val drive_connected: Boolean = false)

data class MetaFile(val index: Int, val path: String, val size: Long)

data class Metadata(
    val id: String,
    val name: String,
    val total_bytes: Long,
    val files: List<MetaFile>,
)

data class MetadataInput(val source: String? = null, val torrent_base64: String? = null)

data class DriveFolder(val id: String, val name: String)

data class DriveFolders(val files: List<DriveFolder>)

data class Selection(val metadata_id: String, val selected: List<Int>, val start: Boolean = true)

data class Limits(
    val tasks: Int? = null,
    val selected_bytes: Long? = null,
    val workspace_bytes: Long = 0,
    val phone_downloads: Boolean = false,
    val admin_mode: Boolean = false,
    val drive_destination_bytes: Long? = null,
)

interface Api {
    @GET("account/limits") suspend fun limits(): Limits

    @GET("server/settings") suspend fun automation(): Automation

    @PUT("server/settings") suspend fun automation(@Body body: Automation): Automation

    @POST("server/cleanup") suspend fun cleanup(): Map<String, Int>

    @GET("server/status") suspend fun status(): Server

    @GET("server/storage") suspend fun storage(): Storage

    @GET("torrents") suspend fun torrents(): List<Torrent>

    @GET("files") suspend fun files(): List<CloudFile>

    @POST("torrents/metadata") suspend fun metadata(@Body body: MetadataInput): Metadata

    @POST("torrents") suspend fun create(@Body body: Selection): Torrent

    @POST("torrents/{id}/pause") suspend fun pause(@Path("id") id: String): Torrent

    @POST("torrents/{id}/resume") suspend fun resume(@Path("id") id: String): Torrent

    @DELETE("files/{id}") suspend fun delete(@Path("id") id: String): Map<String, Boolean>

    @POST("drive/authorize") suspend fun authorizeDrive(): Map<String, String>

    @POST("drive/folders")
    suspend fun createDriveFolder(@Body body: Map<String, String>): DriveFolder

    @GET("drive/folders") suspend fun folders(): DriveFolders

    @PUT("drive/folder") suspend fun folder(@Body body: Map<String, String>): Map<String, String>

    @DELETE("drive") suspend fun disconnectDrive(): Map<String, Boolean>

    @POST("files/{id}/link") suspend fun link(@Path("id") id: String): Map<String, String>

    @GET("account/subscription") suspend fun subscription(): Map<String, Any>
}

class Repository @Inject constructor(val vault: Vault) {
    suspend fun api(): Api {
        val p = vault.context.settings.data.first()
        val url = p[stringPreferencesKey("url")] ?: error("Укажите HTTPS-адрес BotHost")
        validateBaseUrl(url)
        val token = vault.open(p[stringPreferencesKey("token")] ?: "")
        val client =
            OkHttpClient.Builder()
                .readTimeout(90, TimeUnit.SECONDS)
                .addInterceptor { chain ->
                    chain.proceed(
                        chain
                            .request()
                            .newBuilder()
                            .header("Authorization", "Bearer $token")
                            .build()
                    )
                }
                .build()
        return Retrofit.Builder()
            .baseUrl(url.trimEnd('/') + "/")
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(Api::class.java)
    }

    suspend fun connect(url: String, token: String) {
        validateBaseUrl(url)
        vault.context.settings.edit {
            it[stringPreferencesKey("url")] = url
            it[stringPreferencesKey("token")] = vault.seal(token)
        }
        api().status()
    }
}

data class UiState(
    val online: Boolean = false,
    val drive: Boolean = false,
    val storage: Storage = Storage(),
    val torrents: List<Torrent> = emptyList(),
    val files: List<CloudFile> = emptyList(),
    val plan: String = "—",
    val message: String = "Укажите подключение BotHost в настройках",
    val metadata: Metadata? = null,
    val busy: Boolean = false,
    val automation: Automation = Automation(),
    val limits: Limits = Limits(),
    val local: List<Transfer> = emptyList(),
)

@HiltViewModel
class ClientViewModel @Inject constructor(val repo: Repository) : ViewModel() {
    private val mutable = MutableStateFlow(UiState())
    private var metadataGeneration = 0
    val state = mutable.asStateFlow()

    init {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                Transfers.get(repo.vault.context).transfers().observe().collect { rows ->
                    mutable.update { it.copy(local = rows) }
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                mutable.update {
                    it.copy(message = "Локальное хранилище недоступно: " + displayError(e))
                }
            }
        }
        viewModelScope.launch {
            while (isActive) {
                refresh()
                delay(if (mutable.value.online) 5000 else 15000)
            }
        }
    }

    suspend fun refresh() {
        try {
            val a = repo.api()
            val server = a.status()
            val automation = a.automation()
            val torrents = a.torrents()
            val storage = a.storage()
            val files = a.files()
            val sub = a.subscription()
            val limits = a.limits()
            val localPrefs = repo.vault.context.settings.data.first()
            var localError: String? = null
            try {
                if (
                    limits.phone_downloads &&
                        localPrefs[booleanPreferencesKey("auto_phone")] != false &&
                        localPrefs[stringPreferencesKey("folder")] != null
                ) {
                    for (file in files.filter { it.drive_id != null }) queueDownload(
                        repo.vault.context,
                        file,
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                localError = "Передача на Android: " + displayError(e)
            }
            mutable.update {
                it.copy(
                    online = true,
                    automation = automation,
                    limits = limits,
                    drive = server.drive_connected,
                    storage = storage,
                    torrents = torrents,
                    files = files,
                    plan = sub["plan"].toString(),
                    message =
                        localError
                            ?: if (server.drive_connected) ""
                            else "Подключите Google Drive на сервере",
                )
            }
        } catch (e: Exception) {
            if (e is CancellationException) throw e
            mutable.update { it.copy(online = false, message = displayError(e)) }
        }
    }

    fun action(block: suspend () -> Unit) {
        viewModelScope.launch {
            mutable.update { it.copy(busy = true) }
            try {
                block()
                refresh()
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                mutable.update { it.copy(message = displayError(e)) }
            } finally {
                mutable.update { it.copy(busy = false) }
            }
        }
    }

    fun connect(url: String, token: String) = action { repo.connect(url, token) }

    fun disconnect() {
        viewModelScope.launch {
            repo.vault.context.settings.edit {
                it.remove(stringPreferencesKey("url"))
                it.remove(stringPreferencesKey("token"))
            }
            mutable.update { UiState(local = it.local) }
        }
    }

    fun metadata(source: String? = null, bytes: ByteArray? = null) {
        val generation = ++metadataGeneration
        action {
            val m =
                repo
                    .api()
                    .metadata(
                        MetadataInput(
                            source,
                            bytes?.let { Base64.encodeToString(it, Base64.NO_WRAP) },
                        )
                    )
            if (generation == metadataGeneration) mutable.update { it.copy(metadata = m) }
        }
    }

    fun metadataFromUri(uri: android.net.Uri) {
        val generation = ++metadataGeneration
        action {
            val raw =
                withContext(Dispatchers.IO) {
                    repo.vault.context.contentResolver.openInputStream(uri)?.use { input ->
                        val buffer = ByteArray(4 * 1024 * 1024 + 1)
                        var length = 0
                        while (length < buffer.size) {
                            val n = input.read(buffer, length, buffer.size - length)
                            if (n < 0) break
                            length += n
                        }
                        require(length <= 4 * 1024 * 1024) { ".torrent больше 4 МиБ" }
                        buffer.copyOf(length)
                    } ?: error("Не удалось открыть .torrent")
                }
            val result =
                repo
                    .api()
                    .metadata(
                        MetadataInput(torrent_base64 = Base64.encodeToString(raw, Base64.NO_WRAP))
                    )
            if (generation == metadataGeneration) mutable.update { it.copy(metadata = result) }
        }
    }

    fun create(indices: List<Int>) = action {
        val m = mutable.value.metadata ?: return@action
        repo
            .api()
            .create(
                Selection(
                    m.id,
                    indices,
                    repo.vault.context.settings.data.first()[booleanPreferencesKey("auto_start")] !=
                        false,
                )
            )
        mutable.update { it.copy(metadata = null) }
    }

    fun pause(t: Torrent) = action {
        if (t.state == "paused") repo.api().resume(t.id) else repo.api().pause(t.id)
    }

    fun pauseAll() = action {
        val api = repo.api()
        mutable.value.torrents.forEach { api.pause(it.id) }
    }

    fun delete(f: CloudFile) = action { repo.api().delete(f.id) }

    fun dismissMetadata() {
        metadataGeneration++
        mutable.update { it.copy(metadata = null) }
    }

    fun message(s: String) {
        mutable.update { it.copy(message = s) }
    }
}

fun validateBaseUrl(url: String) {
    val u = java.net.URI(url)
    require(
        u.scheme == "https" &&
            u.host != null &&
            u.userInfo == null &&
            u.rawQuery == null &&
            u.rawFragment == null
    ) {
        "Нужен HTTPS URL приложения без логина, пароля и query-параметров"
    }
}

fun displayError(e: Exception): String {
    if (e is retrofit2.HttpException) {
        val code =
            try {
                com.google.gson.JsonParser.parseString(e.response()?.errorBody()?.string())
                    .asJsonObject["error"]
                    .asJsonObject["code"]
                    .asString
            } catch (_: Exception) {
                "http_${e.code()}"
            }
        return mapOf(
            "unauthorized" to "Неверный токен приложения",
            "admin_token_not_configured" to "API token не настроен на сервере",
            "quota_exceeded" to "Выбранные файлы превышают лимит тарифа",
            "task_limit" to "Достигнут лимит задач тарифа",
            "metadata_busy" to "Получение других метаданных ещё не завершено",
            "metadata_timeout" to "Не удалось получить метаданные за отведённое время",
            "google_oauth_not_configured" to "Google OAuth не настроен на сервере",
            "active_batch_wait_or_cancel_task" to "Дождитесь завершения пакета или отмените задачу",
            "file_not_ready" to "Файл ещё не готов",
            "rate_limited" to "Слишком много запросов. Повторите позже",
        )[code] ?: code.replace('_', ' ')
    }
    return e.message ?: "Не удалось выполнить запрос"
}
