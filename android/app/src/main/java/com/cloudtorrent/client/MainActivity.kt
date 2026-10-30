package com.cloudtorrent.client

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.*
import androidx.datastore.preferences.core.*
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.*
import com.caverock.androidsvg.SVG
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

val Bg = Color(0xff10141b)
val RowColor = Color(0xff1a212c)
val Muted = Color(0xff9aa3b2)
val Blue = Color(0xff6cb0ff)
val Purple = Color(0xff8b8cf5)
val Green = Color(0xff7fe0a0)

fun bytes(n: Long): String {
    val format =
        java.text.NumberFormat.getNumberInstance(java.util.Locale.forLanguageTag("ru")).apply {
            maximumFractionDigits = 1
        }
    return when {
        n == 0L -> "0 ГБ"
        n >= 1_000_000_000_000L -> format.format(n / 1_000_000_000_000.0) + " ТБ"
        n >= 1_000_000_000L -> format.format(n / 1_000_000_000.0) + " ГБ"
        n >= 1_000_000L -> format.format(n / 1_000_000.0) + " МБ"
        n >= 1_000L -> format.format(n / 1_000.0) + " КБ"
        else -> "$n Б"
    }
}

fun status(s: String) =
    mapOf(
        "queued" to "В очереди",
        "downloading" to "Скачивание",
        "uploading" to "Передача в Google Drive",
        "checking" to "Проверка",
        "ready" to "Готово",
        "paused" to "Пауза",
        "error" to "Ошибка",
    )[s] ?: s

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        window.statusBarColor = android.graphics.Color.rgb(16, 20, 27)
        window.navigationBarColor = android.graphics.Color.rgb(16, 20, 27)
        androidx.core.view.WindowCompat.setDecorFitsSystemWindows(window, false)
        if (android.os.Build.VERSION.SDK_INT >= 29) window.isNavigationBarContrastEnforced = false
        setContent {
            MaterialTheme(
                colorScheme =
                    darkColorScheme(
                        background = Bg,
                        surface = RowColor,
                        onBackground = Color.White,
                        onSurface = Color.White,
                    )
            ) {
                CompositionLocalProvider(
                    LocalTextStyle provides LocalTextStyle.current.copy(letterSpacing = 0.sp)
                ) {
                    App()
                }
            }
        }
    }
}

@Composable
fun Txt(
    s: String,
    size: Int = 17,
    color: Color = Color.White,
    bold: Boolean = false,
    modifier: Modifier = Modifier,
) {
    Text(
        s,
        color = color,
        fontSize = size.sp,
        lineHeight = referenceLineHeight(size),
        style =
            androidx.compose.ui.text.TextStyle(
                platformStyle =
                    androidx.compose.ui.text.PlatformTextStyle(includeFontPadding = false)
            ),
        letterSpacing = (if (s == "CLOUD TORRENT CLIENT") 0.2 else 0.0).sp,
        fontWeight =
            if (bold && size in listOf(20, 21, 26, 28, 29, 34)) FontWeight.Bold
            else if (bold) FontWeight.SemiBold else FontWeight.Normal,
        modifier = modifier,
    )
}

@Composable
fun IconSvg(index: Int, size: Int = 22, color: Color = Blue) {
    val ctx = LocalContext.current
    val svg =
        remember(index, color) {
            val text =
                ctx.assets
                    .open("icon$index.svg")
                    .bufferedReader()
                    .readText()
                    .replace(
                        "#6cb0ff",
                        String.format("#%06x", color.value.toLong().ushr(32).and(0xffffff)),
                    )
            SVG.getFromString(text)
        }
    Canvas(Modifier.size(size.dp)) {
        drawContext.canvas.nativeCanvas.let { c ->
            val save = c.save()
            svg.documentWidth = this.size.width
            svg.documentHeight = this.size.height
            svg.renderToCanvas(c)
            c.restoreToCount(save)
        }
    }
}

@Composable
fun Card(
    modifier: Modifier = Modifier,
    radius: Int = 22,
    background: Color = RowColor,
    padding: PaddingValues = PaddingValues(16.dp),
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(radius.dp))
            .background(background)
            .padding(padding),
        content = content,
    )
}

@Composable
fun Action(s: String, onClick: () -> Unit) {
    Box(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(Color(0xff263a63))
            .referenceClick(onClick = onClick)
            .padding(13.dp),
        contentAlignment = Alignment.Center,
    ) {
        Txt(s, 17, bold = true)
    }
}

@Composable
fun Bar(p: Double, color: Color = Blue) {
    val progress by
        androidx.compose.animation.core.animateFloatAsState(
            p.toFloat().coerceIn(0f, 1f),
            androidx.compose.animation.core.tween(400),
            label = "referenceProgress",
        )
    Box(
        Modifier.fillMaxWidth()
            .height(7.dp)
            .clip(RoundedCornerShape(4.dp))
            .background(Color(0xff363c4a))
    ) {
        Box(Modifier.fillMaxWidth(progress).fillMaxHeight().background(color))
    }
}

@Composable
fun Setting(
    title: String,
    sub: String? = null,
    value: String? = null,
    icon: Int = 6,
    onClick: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(RowColor)
            .referenceClick(onClick = onClick)
            .padding(16.dp, 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Txt(title)
            if (sub != null) SettingSubtitle(sub)
        }
        if (value != null) Txt(value, 16, Blue, true)
        else IconSvg(icon, 20, if (icon == 6) Muted else Blue)
    }
}

@Composable
fun Toggle(title: String, key: String, default: Boolean = false, sub: String? = null) {
    val ctx = LocalContext.current
    val prefs by ctx.settings.data.collectAsState(initial = emptyPreferences())
    val on = prefs[booleanPreferencesKey(key)] ?: default
    val scope = rememberCoroutineScope()
    Row(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(RowColor)
            .referenceClick {
                scope.launch {
                    ctx.settings.edit { it[booleanPreferencesKey(key)] = !on }
                    if (key in listOf("wifi", "charging", "speed_on"))
                        refreshTransferConstraints(ctx)
                }
            }
            .padding(16.dp, 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Txt(title)
            if (sub != null) SettingSubtitle(sub)
        }
        ReferenceSwitch(on)
    }
}

@Composable
fun Input(
    value: String,
    placeholder: String,
    password: Boolean = false,
    onChange: (String) -> Unit,
) {
    var focused by remember { mutableStateOf(false) }
    BasicTextField(
        value,
        onChange,
        textStyle = androidx.compose.ui.text.TextStyle(color = Color.White, fontSize = 16.sp),
        singleLine = true,
        cursorBrush = androidx.compose.ui.graphics.SolidColor(Color.White),
        visualTransformation =
            if (password) PasswordVisualTransformation() else VisualTransformation.None,
        modifier =
            Modifier.fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(RowColor)
                .border(1.dp, if (focused) Blue else Color(0xff2b3342), RoundedCornerShape(14.dp))
                .onFocusChanged { focused = it.isFocused }
                .padding(14.dp),
        decorationBox = { inner ->
            if (value.isEmpty()) Txt(placeholder, 16, Muted)
            inner()
        },
    )
}

@Composable
fun App(vm: ClientViewModel = viewModel()) {
    val s by vm.state.collectAsState()
    var toastVisible by remember { mutableStateOf(false) }
    LaunchedEffect(s.message, s.busy) {
        if (s.message.isNotEmpty() && !s.busy) {
            toastVisible = true
            kotlinx.coroutines.delay(1800)
            toastVisible = false
        }
    }
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val tab = entry?.destination?.route ?: "downloads"
    val ctx = LocalContext.current
    var folders by remember { mutableStateOf<List<DriveFolder>>(emptyList()) }
    var sheet by remember { mutableStateOf("") }
    var source by remember { mutableStateOf("") }
    var url by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }
    var selected by remember { mutableStateOf<Torrent?>(null) }
    var file by remember { mutableStateOf<CloudFile?>(null) }
    val picker =
        rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) {
                vm.metadataFromUri(uri)
                sheet = ""
            }
        }
    val notificationPermission =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {}
    val folder =
        rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
            if (uri != null) {
                ctx.contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                )
                vm.action {
                    ctx.settings.edit { it[stringPreferencesKey("folder")] = uri.toString() }
                }
            }
        }
    val preferences by ctx.settings.data.collectAsState(initial = emptyPreferences())
    val scope = rememberCoroutineScope()
    val speed = preferences[intPreferencesKey("speed")] ?: 10
    androidx.activity.compose.BackHandler(enabled = sheet.isNotEmpty() || s.metadata != null) {
        vm.dismissMetadata()
        sheet = ""
    }
    val titles =
        mapOf(
            "downloads" to "Загрузки",
            "files" to "Файлы",
            "cloud" to "Облако",
            "settings" to "Настройки",
            "detail" to "Загрузка",
        )
    Box(
        Modifier.fillMaxSize().background(Bg).systemBarsPadding(),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            Modifier.fillMaxSize()
                .background(Bg)
                .padding(start = 20.dp, end = 20.dp, top = 20.dp, bottom = 14.dp)
        ) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Txt("CLOUD TORRENT CLIENT", 14, Color(0xffc3c9d4))
                    Spacer(Modifier.height(2.dp))
                    Txt(titles[tab] ?: "Загрузки", 29, bold = true)
                }
                Box(
                    Modifier.size(40.dp)
                        .clip(RoundedCornerShape(20.dp))
                        .background(Color(0xff1d2430))
                        .referenceClick { nav.navigate("cloud") },
                    contentAlignment = Alignment.Center,
                ) {
                    IconSvg(0)
                }
            }
            NavHost(nav, startDestination = "downloads", modifier = Modifier.weight(1f)) {
                composable("downloads") {
                    Column(Modifier.fillMaxSize()) {
                        Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                            Spacer(Modifier.height(22.dp))
                            Row(
                                Modifier.fillMaxWidth()
                                    .height(51.dp)
                                    .clip(RoundedCornerShape(20.dp))
                                    .background(RowColor)
                                    .referenceTap { sheet = "connect" }
                                    .padding(horizontal = 15.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                IconSvg(1, 24)
                                Spacer(Modifier.width(12.dp))
                                Txt("BotHost", 19)
                                Spacer(Modifier.weight(1f))
                                IconSvg(2, 21, if (s.online) Green else Muted)
                                Spacer(Modifier.width(8.dp))
                                Txt(
                                    if (s.online) "Подключён" else "Не подключён",
                                    16,
                                    if (s.online) Green else Muted,
                                )
                            }
                            Spacer(Modifier.height(12.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                Card(
                                    Modifier.weight(1f),
                                    20,
                                    padding =
                                        PaddingValues(
                                            start = 16.dp,
                                            end = 16.dp,
                                            top = 14.dp,
                                            bottom = 15.dp,
                                        ),
                                ) {
                                    IconSvg(3)
                                    Spacer(Modifier.height(10.dp))
                                    Txt(
                                        s.torrents
                                            .count {
                                                it.state in
                                                    listOf("downloading", "uploading", "checking")
                                            }
                                            .toString(),
                                        28,
                                        bold = true,
                                    )
                                    Spacer(Modifier.height(8.dp))
                                    Txt("Активные", 15, Muted)
                                }
                                Card(
                                    Modifier.weight(1f),
                                    20,
                                    padding =
                                        PaddingValues(
                                            start = 16.dp,
                                            end = 16.dp,
                                            top = 14.dp,
                                            bottom = 15.dp,
                                        ),
                                ) {
                                    IconSvg(4)
                                    Spacer(Modifier.height(10.dp))
                                    Txt(bytes(s.torrents.sumOf { it.total_bytes }), 28, bold = true)
                                    Spacer(Modifier.height(8.dp))
                                    Txt("Объём торрентов", 15, Muted)
                                }
                            }
                            Spacer(Modifier.height(26.dp))
                            Row(
                                Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Txt("Активные загрузки", 21, bold = true)
                                Box(
                                    Modifier.size(26.dp)
                                        .clip(RoundedCornerShape(13.dp))
                                        .background(Color(0xff252a33)),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    Txt(s.torrents.size.toString(), 15, Color(0xffe5e7ec))
                                }
                            }
                            Spacer(Modifier.height(12.dp))
                            s.torrents.forEach { t ->
                                TorrentCard(t) {
                                    selected = t
                                    nav.navigate("detail")
                                }
                                Spacer(Modifier.height(11.dp))
                            }
                            if (s.message.isNotEmpty()) {
                                Text(
                                    s.message,
                                    color = Color(0xff8e97a6),
                                    fontSize = 17.sp,
                                    lineHeight = 23.8.sp,
                                    letterSpacing = 0.sp,
                                    style =
                                        androidx.compose.ui.text.TextStyle(
                                            platformStyle =
                                                androidx.compose.ui.text.PlatformTextStyle(
                                                    includeFontPadding = false
                                                )
                                        ),
                                    modifier = Modifier.padding(top = 14.dp, bottom = 18.dp),
                                )
                            }
                        }
                        Row(
                            Modifier.fillMaxWidth()
                                .clip(RoundedCornerShape(22.dp))
                                .background(RowColor)
                                .referenceClick { sheet = "add" }
                                .padding(16.dp, 14.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            IconSvg(5, 22, Color(0xffc9ced8))
                            Spacer(Modifier.width(14.dp))
                            Column(Modifier.weight(1f)) {
                                Txt("Добавить торрент", 19, bold = true)
                                Spacer(Modifier.height(6.dp))
                                Txt("Magnet / .torrent / URL", 16, Muted)
                            }
                            IconSvg(6, 20, Muted)
                        }
                    }
                }
                composable("files") {
                    val merged =
                        s.files +
                            s.local
                                .filter { local -> s.files.none { it.id == local.fileId } }
                                .map { t ->
                                    CloudFile(
                                        t.fileId,
                                        "",
                                        t.name.ifEmpty {
                                            Uri.decode(t.uri)
                                                .substringAfterLast('/')
                                                .substringAfterLast(':')
                                        },
                                        t.size,
                                        t.state,
                                        null,
                                        t.created,
                                        false,
                                    )
                                }
                    FilesScreen(
                        merged,
                        s.local,
                        onFile = {
                            file = it
                            sheet = "file"
                        },
                    )
                }
                composable("cloud") {
                    val scroll = rememberScrollState()
                    Column(
                        Modifier.fillMaxSize()
                            .referenceFade(scroll)
                            .verticalScroll(scroll)
                            .padding(top = 22.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        ServerToggle(
                            "BotHost",
                            if (s.online) "Подключён" else "Не подключён",
                            s.online,
                        ) {
                            if (s.online) vm.disconnect() else sheet = "connect"
                        }
                        Card {
                            val ratio =
                                if (s.storage.capacity_bytes > 0)
                                    s.storage.used_bytes.toDouble() / s.storage.capacity_bytes
                                else 0.0
                            Row(
                                Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                IconSvg(0, 22)
                                Spacer(Modifier.width(10.dp))
                                Txt("Хранилище", 19, bold = true)
                                Spacer(Modifier.weight(1f))
                                Box(
                                    Modifier.clip(RoundedCornerShape(14.dp))
                                        .background(Color(0xff16304f))
                                        .padding(12.dp, 5.dp)
                                ) {
                                    Txt(
                                        if (s.online) "${(ratio*100).toInt()}%" else "—",
                                        14,
                                        Color(0xff4da3ff),
                                    )
                                }
                            }
                            Spacer(Modifier.height(14.dp))
                            Bar(ratio, if (ratio > .9) Color(0xffff7a7a) else Blue)
                            Spacer(Modifier.height(12.dp))
                            Row(
                                Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                            ) {
                                Txt(
                                    if (s.online)
                                        "${bytes(s.storage.used_bytes)} из ${bytes(s.storage.capacity_bytes)}"
                                    else "Нет данных",
                                    16,
                                    Muted,
                                )
                                Txt(
                                    if (s.online) "свободно ${bytes(s.storage.free_bytes)}"
                                    else "Сервер недоступен",
                                    16,
                                    Muted,
                                )
                            }
                        }
                        GroupLabel("Автоматизация")
                        ServerToggle(
                            "Автосинхронизация",
                            "Загружать завершённые в облако",
                            s.online && s.automation.auto_drive,
                        ) {
                            if (!s.online) sheet = "connect"
                            else if (!s.drive) sheet = "drive"
                            else
                                vm.action {
                                    vm.repo
                                        .api()
                                        .automation(
                                            s.automation.copy(auto_drive = !s.automation.auto_drive)
                                        )
                                }
                        }
                        Toggle(
                            "Автопередача на Android",
                            "auto_phone",
                            true,
                            "Сразу после загрузки в облако",
                        )
                        ServerToggle(
                            "Автоудаление с сервера",
                            "Освобождать место после передачи",
                            s.online && s.automation.auto_delete,
                        ) {
                            if (!s.online) sheet = "connect"
                            else
                                vm.action {
                                    vm.repo
                                        .api()
                                        .automation(
                                            s.automation.copy(
                                                auto_delete = !s.automation.auto_delete
                                            )
                                        )
                                }
                        }
                        ServerToggle("Проверка целостности", "Сверять хеш после загрузки", true) {
                            vm.message(
                                "Проверка pieces и контрольной суммы Drive обязательна и всегда включена"
                            )
                        }
                        ServerToggle(
                            "Автораспаковка архивов",
                            "Распаковывать .zip и .rar в облаке",
                            false,
                        ) {
                            vm.message("Сервер пока не поддерживает автораспаковку архивов")
                        }
                        GroupLabel("Управление")
                        Setting("Одновременные загрузки", "Остальные ждут в очереди", "1") {
                            vm.message("Сервер поддерживает один активный пакет")
                        }
                        Setting("Очистить облако", "Удалить завершённые загрузки", icon = 9) {
                            vm.action { vm.repo.api().cleanup() }
                        }
                    }
                }
                composable("settings") {
                    val scroll = rememberScrollState()
                    Column(
                        Modifier.fillMaxSize()
                            .referenceFade(scroll)
                            .verticalScroll(scroll)
                            .padding(top = 22.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        GroupLabel("Доступ", first = true)
                        Setting(
                            "Профиль",
                            if (!s.online) "Подключите сервер"
                            else if (s.limits.admin_mode) "Без тарифных ограничений"
                            else "Обновите backend для админ-доступа",
                            if (s.limits.admin_mode) "Admin" else s.plan,
                        ) {
                            if (!s.online) sheet = "connect"
                            else
                                vm.message(
                                    if (s.limits.admin_mode)
                                        "Администратор: без лимита размера задач и числа задач; передача на Android разрешена"
                                    else "Обновите backend и включите ADMIN_MODE=true на BotHost"
                                )
                        }
                        GroupLabel("BotHost")
                        Setting(
                            "Подключение по API",
                            if (s.online) "Подключён" else "Не подключён",
                        ) {
                            sheet = "connect"
                        }
                        GroupLabel("Загрузки")
                        Setting(
                            "Папка загрузок",
                            preferences[stringPreferencesKey("folder")]?.let {
                                Uri.decode(it).substringAfterLast(':')
                            } ?: "/Downloads/Torrents",
                        ) {
                            folder.launch(null)
                        }
                        Toggle(
                            "Автозапуск новых",
                            "auto_start",
                            true,
                            "Начинать сразу после добавления",
                        )
                        Setting("Приостановить все", "Для всех активных загрузок", icon = 12) {
                            vm.pauseAll()
                        }
                        GroupLabel("Сеть и питание")
                        Toggle("Только Wi-Fi", "wifi", true)
                        Setting("Лимит мобильного трафика", "Действует вне Wi-Fi", "Без лимита") {
                            vm.message(
                                "Лимит мобильного трафика пока недоступен; используйте Только Wi-Fi"
                            )
                        }
                        Toggle("Ограничить скорость", "speed_on")
                        Setting(
                            "Лимит скорости",
                            "Действует при включённом\nограничении",
                            "$speed МБ/с",
                        ) {
                            scope.launch {
                                val values = listOf(5, 10, 25, 50, 100)
                                ctx.settings.edit {
                                    it[intPreferencesKey("speed")] =
                                        values[(values.indexOf(speed) + 1) % values.size]
                                }
                            }
                        }
                        Toggle(
                            "Только при зарядке",
                            "charging",
                            sub = "Приостанавливать при разрядке",
                        )
                        ServerToggle("Ночной режим", "Загружать с 01:00 до 07:00", false) {
                            vm.message("Ночное расписание пока недоступно")
                        }
                        GroupLabel("Уведомления")
                        ServerToggle(
                            "Уведомления",
                            null,
                            androidx.core.app.NotificationManagerCompat.from(ctx)
                                .areNotificationsEnabled(),
                        ) {
                            if (android.os.Build.VERSION.SDK_INT >= 33)
                                notificationPermission.launch(
                                    android.Manifest.permission.POST_NOTIFICATIONS
                                )
                            ctx.startActivity(
                                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                                    .putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName)
                            )
                        }
                        GroupLabel("Безопасность")
                        ServerToggle("Защита приложения", "Вход по отпечатку или PIN-коду", false) {
                            vm.message(
                                "Блокировка входа пока недоступна; локальные секреты защищены Android Keystore"
                            )
                        }
                    }
                }
                composable("detail") {
                    selected?.let { old ->
                        val t = s.torrents.find { it.id == old.id } ?: old
                        DetailScreen(t, s.files, { nav.popBackStack() }, { vm.pause(t) }, vm)
                    }
                }
            }
            Spacer(Modifier.height(6.dp))
            Row(
                Modifier.fillMaxWidth()
                    .padding(start = 4.dp, end = 4.dp, top = 12.dp, bottom = 2.dp)
            ) {
                listOf("downloads", "files", "cloud", "settings").forEachIndexed { i, t ->
                    Column(
                        Modifier.weight(1f).referenceTap {
                            nav.navigate(t) { launchSingleTop = true }
                        },
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        IconSvg(
                            listOf(14, 15, 16, 17)[i],
                            25,
                            if (tab == t || tab == "detail" && t == "downloads") Color.White
                            else Color(0xff8c93a1),
                        )
                        Spacer(Modifier.height(5.dp))
                        Txt(
                            titles[t]!!,
                            14,
                            if (tab == t || tab == "detail" && t == "downloads") Color.White
                            else Color(0xff8c93a1),
                        )
                    }
                }
            }
        }
    }
    if (sheet.isNotEmpty() || s.metadata != null) {
        Box(
            Modifier.fillMaxSize().systemBarsPadding().imePadding(),
            contentAlignment = Alignment.Center,
        ) {
            Box(
                Modifier.fillMaxSize().background(Color.Black.copy(alpha = .6f)).referenceTap {
                    sheet = ""
                },
                contentAlignment = Alignment.BottomCenter,
            ) {
                Column(
                    Modifier.fillMaxWidth()
                        .clip(RoundedCornerShape(topStart = 26.dp, topEnd = 26.dp))
                        .background(if (sheet == "plans") Bg else Color(0xff161c26))
                        .referenceTap {}
                        .padding(
                            horizontal = if (sheet == "plans") 9.dp else 20.dp,
                            vertical = 22.dp,
                        )
                        .heightIn(
                            max =
                                (androidx.compose.ui.platform.LocalConfiguration.current
                                        .screenHeightDp * .9f)
                                    .dp
                        )
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement =
                        Arrangement.spacedBy(
                            if (sheet in listOf("add", "link", "connect", "plans", "file")) 0.dp
                            else 12.dp
                        ),
                ) {
                    if (s.metadata != null) {
                        val m = s.metadata!!
                        var indices by
                            remember(m.id) { mutableStateOf(m.files.map { it.index }.toSet()) }
                        Txt(m.name, 20, bold = true)
                        Txt(
                            "Всего ${bytes(m.total_bytes)} · выбрано ${bytes(m.files.filter{it.index in indices}.sumOf{it.size})}",
                            14,
                            Muted,
                        )
                        androidx.compose.foundation.lazy.LazyColumn(
                            Modifier.heightIn(max = 350.dp)
                        ) {
                            items(m.files.size) { i ->
                                val f = m.files[i]
                                Setting(
                                    f.path,
                                    bytes(f.size),
                                    if (f.index in indices) "✓" else "○",
                                ) {
                                    indices =
                                        if (f.index in indices) indices - f.index
                                        else indices + f.index
                                }
                            }
                        }
                        Cancel("Отмена") {
                            vm.dismissMetadata()
                            sheet = ""
                        }
                        Action("Начать загрузку") {
                            vm.create(indices.toList())
                            sheet = ""
                        }
                    } else
                        when (sheet) {
                            "add" -> {
                                Txt("Добавить торрент", 20, bold = true)
                                Spacer(Modifier.height(14.dp))
                                Choice("Файлом", "Выбрать .torrent", 18) {
                                    picker.launch(
                                        arrayOf(
                                            "application/x-bittorrent",
                                            "application/octet-stream",
                                            "*/*",
                                        )
                                    )
                                }
                                Spacer(Modifier.height(11.dp))
                                Choice("Ссылкой", "Magnet или URL", 20) { sheet = "link" }
                                Spacer(Modifier.height(14.dp))
                                Cancel("Отмена") { sheet = "" }
                            }
                            "link" -> {
                                Txt("Добавить по ссылке", 20, bold = true)
                                Spacer(Modifier.height(14.dp))
                                Input(source, "Magnet-ссылка или URL") { source = it }
                                Spacer(Modifier.height(14.dp))
                                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                    Box(Modifier.weight(1f)) { Cancel("Назад") { sheet = "add" } }
                                    Box(Modifier.weight(1f)) {
                                        Action(if (s.busy) "Метаданные…" else "Добавить") {
                                            vm.metadata(source)
                                            sheet = ""
                                        }
                                    }
                                }
                            }
                            "connect" -> {
                                Txt("BotHost API", 20, bold = true)
                                Spacer(Modifier.height(14.dp))
                                Input(url, "HTTPS-адрес сервера") { url = it }
                                Spacer(Modifier.height(10.dp))
                                Input(token, "Пароль сервера (ADMIN_API_TOKEN)", true) {
                                    token = it
                                }
                                Spacer(Modifier.height(10.dp))
                                Txt(
                                    "Адрес начинается с https://. Пароль — значение ADMIN_API_TOKEN в переменных проекта BotHost.",
                                    14,
                                    Muted,
                                )
                                Spacer(Modifier.height(14.dp))
                                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                    Box(Modifier.weight(1f)) { Cancel("Отмена") { sheet = "" } }
                                    Box(Modifier.weight(1f)) {
                                        SheetButton("Подключить", primary = true) {
                                            vm.connect(url, token)
                                            token = ""
                                            sheet = ""
                                        }
                                    }
                                }
                                if (s.online) {
                                    Spacer(Modifier.height(10.dp))
                                    Cancel("Отключить") {
                                        vm.disconnect()
                                        sheet = ""
                                    }
                                }
                            }
                            "plans" -> {
                                Row(
                                    Modifier.fillMaxWidth().height(IntrinsicSize.Min),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                ) {
                                    listOf(false, true).forEach { premium ->
                                        PlanCard(premium, Modifier.weight(1f).fillMaxHeight()) {
                                            if (premium)
                                                vm.message(
                                                    "Оплата пока не подключена. Premium не активирован"
                                                )
                                            sheet = ""
                                        }
                                    }
                                }
                            }
                            "drive" -> {
                                Txt("Google Drive", 20, bold = true)
                                Setting("Подключить Google", "OAuth 2.0 в браузере") {
                                    vm.action {
                                        val result = vm.repo.api().authorizeDrive()
                                        ctx.startActivity(
                                            Intent(Intent.ACTION_VIEW, Uri.parse(result["url"]))
                                        )
                                    }
                                }
                                Setting("Выбрать папку", "Доступные приложению папки") {
                                    vm.action {
                                        folders = vm.repo.api().folders().files
                                        sheet = "folders"
                                    }
                                }
                                Setting("Отключить Google Drive") {
                                    vm.action { vm.repo.api().disconnectDrive() }
                                    sheet = ""
                                }
                            }
                            "folders" -> {
                                Setting("Создать папку", "Cloud Torrent Client") {
                                    vm.action {
                                        vm.repo
                                            .api()
                                            .createDriveFolder(
                                                mapOf("name" to "Cloud Torrent Client")
                                            )
                                    }
                                    sheet = ""
                                }
                                Txt("Папка Google Drive", 20, bold = true)
                                if (folders.isEmpty())
                                    Txt(
                                        "Нет доступных папок. Нужна папка, предоставленная OAuth-приложению",
                                        14,
                                        Muted,
                                    )
                                folders.forEach { folder ->
                                    Setting(folder.name) {
                                        vm.action { vm.repo.api().folder(mapOf("id" to folder.id)) }
                                        sheet = ""
                                    }
                                }
                            }
                            "file" ->
                                file?.let { f ->
                                    Row(
                                        Modifier.fillMaxWidth(),
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        FileTypeIcon(category(f.path))
                                        Spacer(Modifier.width(14.dp))
                                        Column(
                                            Modifier.weight(1f).referenceTap {
                                                f.drive_id?.let {
                                                    ctx.startActivity(
                                                        Intent(
                                                            Intent.ACTION_VIEW,
                                                            Uri.parse(
                                                                "https://drive.google.com/file/d/$it/view"
                                                            ),
                                                        )
                                                    )
                                                }
                                            }
                                        ) {
                                            Text(
                                                f.path.substringAfterLast('/'),
                                                color = Color.White,
                                                fontSize = 19.sp,
                                                fontWeight = FontWeight.SemiBold,
                                                maxLines = 1,
                                                overflow =
                                                    androidx.compose.ui.text.style.TextOverflow
                                                        .Ellipsis,
                                                style =
                                                    androidx.compose.ui.text.TextStyle(
                                                        platformStyle =
                                                            androidx.compose.ui.text
                                                                .PlatformTextStyle(
                                                                    includeFontPadding = false
                                                                )
                                                    ),
                                            )
                                            Spacer(Modifier.height(4.dp))
                                            Txt(
                                                bytes(f.size) + ", " + category(f.path).lowercase(),
                                                15,
                                                Muted,
                                            )
                                        }
                                    }
                                    Spacer(Modifier.height(16.dp))
                                    val local = s.local.firstOrNull { it.fileId == f.id }
                                    val onPhone = local?.state == "ready"
                                    val active = local?.state in listOf("downloading", "queued")
                                    FileAction(
                                        if (onPhone) "Уже на Android"
                                        else if (active) "Передача на Android"
                                        else "Скачать на Android",
                                        if (onPhone) "Файл скачан на устройство"
                                        else if (local != null)
                                            "${bytes(local.offset)} / ${bytes(local.size)}"
                                        else if (s.limits.phone_downloads) "Передача начнётся сразу"
                                        else "Требуется админ-доступ на сервере",
                                        if (onPhone) 31 else 32,
                                        if (onPhone) Green else Purple,
                                        enabled = !onPhone,
                                    ) {
                                        if (!s.online) sheet = "connect"
                                        else if (!s.limits.phone_downloads)
                                            vm.message(
                                                "Обновите backend и включите ADMIN_MODE=true на BotHost"
                                            )
                                        else {
                                            if (active && local != null)
                                                androidx.work.WorkManager.getInstance(ctx)
                                                    .cancelUniqueWork(local.id)
                                            else if (local != null)
                                                resumeDownload(ctx, local.id, vm)
                                            else enqueueDownload(ctx, f, vm)
                                            sheet = ""
                                        }
                                    }

                                    Spacer(Modifier.height(9.dp))
                                    FileAction(
                                        if (local != null && s.files.none { it.id == f.id })
                                            "Поделиться файлом"
                                        else "Скопировать ссылку",
                                        icon = 20,
                                    ) {
                                        if (local != null && s.files.none { it.id == f.id }) {
                                            ctx.startActivity(
                                                Intent.createChooser(
                                                    Intent(Intent.ACTION_SEND)
                                                        .setType("application/octet-stream")
                                                        .putExtra(
                                                            Intent.EXTRA_STREAM,
                                                            Uri.parse(local.uri),
                                                        )
                                                        .addFlags(
                                                            Intent.FLAG_GRANT_READ_URI_PERMISSION
                                                        ),
                                                    "Поделиться файлом",
                                                )
                                            )
                                        } else
                                            vm.action {
                                                val link = vm.repo.api().link(f.id)
                                                val prefs = ctx.settings.data.first()
                                                val full =
                                                    prefs[stringPreferencesKey("url")]!!.trimEnd(
                                                        '/'
                                                    ) + link["path"]
                                                (ctx.getSystemService(
                                                        android.content.Context.CLIPBOARD_SERVICE
                                                    ) as android.content.ClipboardManager)
                                                    .setPrimaryClip(
                                                        android.content.ClipData.newPlainText(
                                                            "Cloud Torrent Client",
                                                            full,
                                                        )
                                                    )
                                            }
                                        sheet = ""
                                    }
                                    Spacer(Modifier.height(9.dp))
                                    val localOnly = local != null && s.files.none { it.id == f.id }
                                    FileAction(
                                        if (localOnly) "Удалить с Android" else "Удалить из облака",
                                        icon = 9,
                                        color = Color(0xffff8f8f),
                                    ) {
                                        if (localOnly && local != null)
                                            vm.action {
                                                androidx.work.WorkManager.getInstance(ctx)
                                                    .cancelUniqueWork(local.id)
                                                val document =
                                                    androidx.documentfile.provider.DocumentFile
                                                        .fromSingleUri(ctx, Uri.parse(local.uri))
                                                require(document?.delete() == true) {
                                                    "Не удалось удалить файл. Проверьте доступ к папке"
                                                }
                                                Transfers.get(ctx).transfers().delete(local)
                                            }
                                        else vm.delete(f)
                                        sheet = ""
                                    }
                                    Spacer(Modifier.height(12.dp))
                                    Cancel("Закрыть") { sheet = "" }
                                }
                        }
                }
            }
        }
    }
    if (toastVisible)
        Box(Modifier.fillMaxSize().systemBarsPadding(), contentAlignment = Alignment.Center) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.BottomCenter) {
                Box(
                    Modifier.padding(bottom = 92.dp)
                        .clip(RoundedCornerShape(14.dp))
                        .background(Color(0xff2b3342))
                        .padding(horizontal = 16.dp, vertical = 10.dp)
                ) {
                    Text(
                        s.message,
                        color = Color.White,
                        fontSize = 14.sp,
                        letterSpacing = 0.sp,
                        maxLines = 1,
                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                    )
                }
            }
        }
}

@Composable
fun TorrentCard(t: Torrent, onClick: () -> Unit) {
    Card(
        Modifier.alpha(if (t.state == "paused") 0.65f else 1f).referenceClick(onClick = onClick),
        padding = PaddingValues(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconSvg(22, 22, Color(0xffc9ced8))
            Spacer(Modifier.width(10.dp))
            Text(
                t.name,
                color = Color.White,
                fontSize = 19.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(6.dp))
            Box(
                Modifier.clip(RoundedCornerShape(14.dp))
                    .background(if (t.state == "ready") Color(0xff173a2a) else Color(0xff16304f))
                    .padding(9.dp, 3.dp)
            ) {
                Txt(
                    if (t.state == "downloading") "BotHost"
                    else if (t.state == "uploading") "Drive" else status(t.state),
                    12,
                    if (t.state == "ready") Green else Blue,
                )
            }
            Spacer(Modifier.width(14.dp))
            Box(Modifier.widthIn(min = 48.dp), contentAlignment = Alignment.CenterEnd) {
                Txt("${((t.phase_progress ?: t.progress)*100).toInt()}%", 19, bold = true)
            }
        }
        Spacer(Modifier.height(14.dp))
        Bar((t.phase_progress ?: t.progress), if (t.state == "uploading") Purple else Blue)
        Spacer(Modifier.height(11.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            val eta =
                if (t.eta_seconds != null && t.state !in listOf("paused", "error"))
                    " · этап ~${maxOf(1,(t.eta_seconds+59)/60)} мин"
                else ""
            Txt(bytes(t.total_bytes) + eta, 16, Muted)
            Txt(if (t.speed > 0) bytes(t.speed) + "/с" else status(t.state), 16, Muted)
        }
    }
}

fun category(path: String): String =
    when (path.substringAfterLast('.').lowercase()) {
        "iso",
        "img",
        "dmg" -> "Образы"
        "zip",
        "rar",
        "7z",
        "gz",
        "tar" -> "Архивы"
        "mp4",
        "mkv",
        "avi",
        "mov",
        "webm" -> "Видео"
        "mp3",
        "flac",
        "wav",
        "aac",
        "ogg" -> "Аудио"
        else -> "Прочее"
    }

@Composable
fun FilesScreen(
    files: List<CloudFile>,
    local: List<Transfer> = emptyList(),
    onFile: (CloudFile) -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var filter by remember { mutableStateOf("Все") }
    val filesScroll = rememberScrollState()
    Column(
        Modifier.fillMaxSize()
            .referenceFade(filesScroll)
            .verticalScroll(filesScroll)
            .padding(top = 20.dp)
    ) {
        Card(
            radius = 24,
            padding = PaddingValues(start = 18.dp, end = 18.dp, top = 18.dp, bottom = 16.dp),
        ) {
            Txt(bytes(files.sumOf { it.size }), 34, bold = true)
            Spacer(Modifier.height(8.dp))
            Txt("${files.size} ${fileCountWord(files.size)} в облаке", 15, Muted)
            Spacer(Modifier.height(18.dp))
            val groups =
                files
                    .groupBy { category(it.path) }
                    .toList()
                    .sortedByDescending { (_, v) -> v.sumOf { it.size } }
                    .toMap()
            Row(
                Modifier.fillMaxWidth().height(10.dp),
                horizontalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                groups.entries.forEachIndexed { i, g ->
                    Box(
                        Modifier.weight(g.value.sumOf { it.size }.toFloat().coerceAtLeast(1f))
                            .fillMaxHeight()
                            .clip(RoundedCornerShape(5.dp))
                            .background(categoryColor(g.key))
                    )
                }
            }
            Spacer(Modifier.height(16.dp))
            groups.entries.chunked(2).forEachIndexed { rowIndex, pair ->
                if (rowIndex > 0) Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    pair.forEach { (k, v) ->
                        Row(Modifier.weight(1f), horizontalArrangement = Arrangement.SpaceBetween) {
                            Box(
                                Modifier.size(8.dp)
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(categoryColor(k))
                            )
                            Spacer(Modifier.width(8.dp))
                            Txt(k, 14, Muted)
                            Spacer(Modifier.weight(1f))
                            Txt(bytes(v.sumOf { it.size }), 14, bold = true)
                        }
                    }
                    if (pair.size == 1) Spacer(Modifier.weight(1f))
                }
            }
        }
        Spacer(Modifier.height(14.dp))
        SearchField(query) { query = it }
        Row(
            Modifier.fillMaxWidth()
                .padding(top = 12.dp, bottom = 4.dp)
                .referenceHorizontalFade()
                .horizontalScroll(rememberScrollState())
                .padding(end = 24.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            listOf("Все", "Образы", "Архивы", "Видео", "Аудио").forEach { c ->
                Box(
                    Modifier.clip(RoundedCornerShape(18.dp))
                        .background(if (c == filter) Color.White else RowColor)
                        .referenceTap { filter = c }
                        .padding(15.dp, 9.dp)
                ) {
                    Txt(c, 15, if (c == filter) Color(0xff0b0e13) else Color(0xffb5bcc9), true)
                }
            }
        }
        val filtered =
            files.filter {
                (filter == "Все" || category(it.path) == filter) && it.path.contains(query, true)
            }
        if (filtered.isEmpty())
            Column(
                Modifier.fillMaxWidth()
                    .padding(start = 24.dp, end = 24.dp, top = 48.dp, bottom = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                IconSvg(29, 34, Color(0xff4a5363))
                Spacer(Modifier.height(10.dp))
                Text(
                    "Ничего не найдено",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                    letterSpacing = 0.sp,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    "Измените запрос или выберите другой тип файлов.",
                    fontSize = 14.sp,
                    lineHeight = 20.3.sp,
                    color = Muted,
                    textAlign = TextAlign.Center,
                    letterSpacing = 0.sp,
                )
            }
        if (filtered.isNotEmpty())
            for ((groupName, groupFiles) in
                filtered
                    .groupBy { fileDay(it.created) }
                    .toSortedMap(
                        compareBy {
                            when (it) {
                                "Сегодня" -> 0
                                "Вчера" -> 1
                                else -> 2
                            }
                        }
                    )) {
                Txt(
                    groupName,
                    15,
                    Muted,
                    true,
                    Modifier.padding(start = 4.dp, top = 22.dp, bottom = 9.dp),
                )
                Column(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(RowColor)
                ) {
                    groupFiles.forEachIndexed { i, f ->
                        if (i > 0)
                            Box(
                                Modifier.fillMaxWidth()
                                    .height(1.dp)
                                    .background(Color.White.copy(alpha = .06f))
                            )
                        Row(
                            Modifier.fillMaxWidth()
                                .referenceTap { onFile(f) }
                                .padding(start = 12.dp, end = 14.dp, top = 12.dp, bottom = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            val cat = category(f.path)
                            FileTypeIcon(cat)
                            Spacer(Modifier.width(13.dp))
                            Column(Modifier.weight(1f)) {
                                Text(
                                    f.path.substringAfterLast('/'),
                                    color = Color.White,
                                    fontSize = 17.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    maxLines = 1,
                                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                                )
                                Spacer(Modifier.height(5.dp))
                                Txt(
                                    "${bytes(f.size)} · " +
                                        listOfNotNull(
                                                if (f.server_present) "BotHost" else null,
                                                if (f.drive_id != null) "Drive" else null,
                                                if (
                                                    local.any {
                                                        it.fileId == f.id && it.state == "ready"
                                                    }
                                                )
                                                    "Android"
                                                else null,
                                            )
                                            .joinToString(" · ")
                                            .ifEmpty { status(f.state) },
                                    14,
                                    Muted,
                                )
                            }
                            IconSvg(6, 18, Color(0xff5d6676))
                        }
                    }
                }
            }
    }
}

@Composable
fun Choice(title: String, sub: String, icon: Int, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth()
            .height(78.dp)
            .clip(RoundedCornerShape(22.dp))
            .background(RowColor)
            .referenceClick(onClick = onClick)
            .padding(16.dp, 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconSvg(icon, 22, Color(0xffc9ced8))
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Txt(title, 19, bold = true)
            Spacer(Modifier.height(5.dp))
            Txt(sub, 16, Muted)
        }
        IconSvg(6, 20, Muted)
    }
}

@Composable
fun Cancel(title: String, onClick: () -> Unit) {
    Box(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Color(0xff252a33))
            .referenceClick(onClick = onClick)
            .padding(13.dp),
        contentAlignment = Alignment.Center,
    ) {
        Txt(title, 16, bold = true)
    }
}

@Composable
fun DetailScreen(
    t: Torrent,
    files: List<CloudFile>,
    back: () -> Unit,
    pause: () -> Unit,
    vm: ClientViewModel,
) {
    var phone by remember { mutableStateOf(false) }
    val ctx = LocalContext.current
    val transfers by Transfers.get(ctx).transfers().observe().collectAsState(initial = emptyList())
    val ids = files.filter { it.task_id == t.id }.map { it.id }
    val local = transfers.filter { it.fileId in ids }
    val total = local.sumOf { it.size }
    val done = local.sumOf { it.offset }
    val pct =
        if (phone) if (total > 0) done.toDouble() / total else 0.0
        else (t.phase_progress ?: t.progress)
    val color = if (phone) Purple else Blue
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(top = 18.dp)) {
        Row(Modifier.clickable(onClick = back), verticalAlignment = Alignment.CenterVertically) {
            IconSvg(13, 20)
            Txt("Назад", 16, Blue)
        }
        Spacer(Modifier.height(16.dp))
        Row {
            listOf(false, true).forEach { isPhone ->
                Box(
                    Modifier.weight(1f)
                        .clip(RoundedCornerShape(26.dp))
                        .background(if (phone == isPhone) Color(0xff2a2b2e) else Color.Transparent)
                        .referenceTap { phone = isPhone }
                        .padding(vertical = 14.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Txt(
                        if (isPhone) "Android" else "Cloud",
                        18,
                        if (phone == isPhone) Color.White else Muted,
                        true,
                    )
                }
            }
        }
        Spacer(Modifier.height(12.dp))
        Card {
            Row {
                Text(
                    if (phone) t.name else t.phase_file?.substringAfterLast('/') ?: t.name,
                    color = Color.White,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Txt("${(pct*100).toInt()}%", 21, color, true)
            }
            Spacer(Modifier.height(14.dp))
            Bar(pct, color)
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Txt(
                    if (phone) if (done == total && total > 0) "Готово" else "Передача"
                    else if (t.speed > 0) bytes(t.speed) + "/с" else status(t.state),
                    16,
                    Muted,
                )
                Txt(
                    "${bytes(if(phone)done else t.phase_completed_bytes ?: (t.total_bytes*pct).toLong())} / ${bytes(if(phone)total else t.phase_total_bytes ?:t.total_bytes)}",
                    16,
                    Muted,
                )
            }
            Spacer(Modifier.height(14.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconSvg(if (phone) 26 else 25, 22, color)
                Spacer(Modifier.width(8.dp))
                Txt(
                    if (phone) "На Android-устройство"
                    else if (t.state == "uploading") "Передача в Google Drive"
                    else if (t.state == "checking") "Проверка файла" else "На сервер BotHost",
                    16,
                    Muted,
                )
            }
        }
        Spacer(Modifier.height(16.dp))
        if (phone) {
            files
                .filter { it.task_id == t.id && it.drive_id != null }
                .forEach { f ->
                    Setting(f.path.substringAfterLast('/'), "Скачать на Android") {
                        if (vm.state.value.limits.phone_downloads) enqueueDownload(ctx, f, vm)
                        else vm.message("Обновите backend и включите ADMIN_MODE=true на BotHost")
                    }
                    Spacer(Modifier.height(9.dp))
                }
        } else Action(if (t.state == "paused") "Возобновить" else "Приостановить", pause)
        t.error?.let {
            Spacer(Modifier.height(14.dp))
            Txt(readableTaskError(it), 14, Color(0xffff8f8f))
        }
    }
}

@Composable
fun ServerToggle(title: String, sub: String?, on: Boolean, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(RowColor)
            .referenceClick(onClick = onClick)
            .padding(16.dp, 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Txt(title)
            if (sub != null) SettingSubtitle(sub)
        }
        ReferenceSwitch(on)
    }
}

@Composable
fun SearchField(value: String, onChange: (String) -> Unit) {
    var focused by remember { mutableStateOf(false) }
    Row(
        Modifier.fillMaxWidth()
            .height(46.dp)
            .clip(RoundedCornerShape(16.dp))
            .background(RowColor)
            .border(
                1.dp,
                if (focused) Color(0xff3b5f99) else Color.Transparent,
                RoundedCornerShape(16.dp),
            )
            .padding(start = 15.dp, end = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconSvg(7, 20, Muted)
        Spacer(Modifier.width(9.dp))
        BasicTextField(
            value,
            onChange,
            modifier = Modifier.weight(1f).onFocusChanged { focused = it.isFocused },
            singleLine = true,
            cursorBrush = androidx.compose.ui.graphics.SolidColor(Color.White),
            textStyle =
                androidx.compose.ui.text.TextStyle(
                    color = Color.White,
                    fontSize = 16.sp,
                    letterSpacing = 0.sp,
                ),
            decorationBox = { inner ->
                if (value.isEmpty()) Txt("Поиск по файлам", 16, Color(0xff7d8696))
                inner()
            },
        )
    }
}

fun categoryColor(category: String): Color =
    when (category) {
        "Образы" -> Blue
        "Архивы" -> Color(0xff9d9ef7)
        "Видео" -> Color(0xfff0b86e)
        "Аудио" -> Green
        else -> Color(0xffaab2c0)
    }

fun fileDay(created: Double): String {
    val today = java.time.LocalDate.now()
    val date =
        java.time.Instant.ofEpochSecond(created.toLong())
            .atZone(java.time.ZoneId.systemDefault())
            .toLocalDate()
    return if (date == today) "Сегодня" else if (date == today.minusDays(1)) "Вчера" else "Ранее"
}

@Composable
fun FileAction(
    title: String,
    sub: String? = null,
    icon: Int,
    color: Color = Blue,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth()
            .alpha(if (enabled) 1f else .6f)
            .clip(RoundedCornerShape(18.dp))
            .background(RowColor)
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconSvg(icon, 22, color)
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Txt(title, 17, if (color == Color(0xffff8f8f)) color else Color.White, true)
            if (sub != null) {
                Spacer(Modifier.height(3.dp))
                Txt(sub, 14, Muted)
            }
        }
    }
}

fun readableTaskError(code: String): String =
    when (code) {
        "workspace_or_single_file_limit" ->
            "Файл не помещается в рабочий диск BotHost с техническим резервом. Потоковая передача такого файла ещё не поддерживается. Это физическое ограничение сервера, а не тариф."
        "disk_safety_reserve",
        "workspace_capacity_changed",
        "workspace_disk_full" ->
            "Недостаточно свободного рабочего места на BotHost. Освободите диск или увеличьте доступное пространство."
        else -> code.replace('_', ' ')
    }
