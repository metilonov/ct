package com.cloudtorrent.client

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.*
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.graphics.*
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

fun Modifier.referenceClick(onClick: () -> Unit): Modifier = composed {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by
        animateFloatAsState(if (pressed) .97f else 1f, tween(150), label = "referencePress")
    graphicsLayer {
            scaleX = scale
            scaleY = scale
        }
        .clickable(interactionSource = interaction, indication = null, onClick = onClick)
}

fun Modifier.referenceFade(scroll: ScrollState): Modifier =
    graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
        .drawWithContent {
            drawContent()
            val fade = minOf(36.dp.toPx(), size.height / 2)
            if (size.height > 0 && (scroll.value > 0 || scroll.canScrollForward)) {
                val top = if (scroll.value > 0) fade / size.height else 0f
                val bottom = if (scroll.canScrollForward) 1f - fade / size.height else 1f
                drawRect(
                    Brush.verticalGradient(
                        0f to if (top > 0) Color.Transparent else Color.Black,
                        top to Color.Black,
                        bottom to Color.Black,
                        1f to if (bottom < 1) Color.Transparent else Color.Black,
                    ),
                    blendMode = BlendMode.DstIn,
                )
            }
        }

@Composable
fun GroupLabel(title: String, first: Boolean = false) {
    Text(
        title.uppercase(java.util.Locale.forLanguageTag("ru")),
        color = Muted,
        fontSize = 13.sp,
        lineHeight = 15.sp,
        letterSpacing = .3.sp,
        style =
            androidx.compose.ui.text.TextStyle(
                platformStyle =
                    androidx.compose.ui.text.PlatformTextStyle(includeFontPadding = false)
            ),
        modifier = Modifier.padding(start = 4.dp, end = 4.dp, top = if (first) 0.dp else 12.dp),
    )
}

@Composable
fun SheetButton(title: String, primary: Boolean = false, onClick: () -> Unit) {
    Box(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(if (primary) Color(0xff263a63) else Color(0xff252a33))
            .referenceClick(onClick)
            .padding(13.dp),
        contentAlignment = androidx.compose.ui.Alignment.Center,
    ) {
        Txt(title, 16, bold = true)
    }
}

@Composable
fun PlanCard(premium: Boolean, modifier: Modifier, onClick: () -> Unit) {
    Column(
        modifier
            .clip(RoundedCornerShape(18.dp))
            .background(RowColor)
            .border(1.dp, Color.White.copy(alpha = .06f), RoundedCornerShape(18.dp))
            .padding(start = 12.dp, end = 12.dp, top = 15.dp, bottom = 13.dp)
    ) {
        Box(
            Modifier.clip(RoundedCornerShape(15.dp))
                .background(if (premium) Color(0xff16304f) else Color(0xff252a33))
                .padding(horizontal = 12.dp, vertical = 6.dp)
        ) {
            Txt(
                if (premium) "PREMIUM" else "FREE",
                12,
                if (premium) Color(0xff4da3ff) else Color(0xffcfd4dd),
                true,
            )
        }
        Spacer(Modifier.height(16.dp))
        Row(verticalAlignment = androidx.compose.ui.Alignment.Bottom) {
            Text(
                if (premium) "$4.99" else "$0",
                color = Color.White,
                fontSize = 26.sp,
                lineHeight = 26.sp,
                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                style =
                    androidx.compose.ui.text.TextStyle(
                        platformStyle =
                            androidx.compose.ui.text.PlatformTextStyle(includeFontPadding = false)
                    ),
            )
            if (premium) {
                Spacer(Modifier.width(4.dp))
                Txt("/ мес.", 12, Color(0xff9a9ea6), true)
            }
        }
        Spacer(Modifier.height(14.dp))
        Text(
            if (premium) "Расширенные возможности" else "Бесплатно навсегда",
            fontSize = 13.sp,
            lineHeight = 17.55.sp,
            color = Color(0xff8d9097),
            style =
                androidx.compose.ui.text.TextStyle(
                    platformStyle =
                        androidx.compose.ui.text.PlatformTextStyle(includeFontPadding = false)
                ),
            modifier = Modifier.heightIn(min = 35.1.dp),
        )
        Spacer(Modifier.height(14.dp))
        Box(Modifier.fillMaxWidth().height(1.dp).background(Color.White.copy(alpha = .09f)))
        Spacer(Modifier.height(16.dp))
        val benefits =
            if (premium)
                listOf(
                    "До 5 торрентов",
                    "До 500 ГБ на задачу",
                    "Google Drive + телефон",
                    "Приоритет в очереди",
                    "Без рекламы",
                )
            else
                listOf(
                    "1 активный торрент",
                    "До 20 ГБ на задачу",
                    "Google Drive",
                    "Базовая очередь",
                    "Реклама",
                )
        benefits.forEachIndexed { index, text ->
            if (index > 0) Spacer(Modifier.height(12.dp))
            Row {
                Txt("✓", 13, Green)
                Spacer(Modifier.width(6.dp))
                Text(
                    text,
                    fontSize = 13.sp,
                    lineHeight = 16.9.sp,
                    color = Color.White,
                    style =
                        androidx.compose.ui.text.TextStyle(
                            platformStyle =
                                androidx.compose.ui.text.PlatformTextStyle(
                                    includeFontPadding = false
                                )
                        ),
                )
            }
        }
        Spacer(Modifier.weight(1f))
        Spacer(Modifier.height(16.dp))
        Box(
            Modifier.fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(Color(0xff252a33))
                .referenceClick(onClick)
                .padding(vertical = 11.dp),
            contentAlignment = androidx.compose.ui.Alignment.Center,
        ) {
            Txt(if (premium) "Подписаться" else "Остаться", 14, bold = true)
        }
    }
}

fun fileCountWord(n: Int) =
    when {
        n % 100 in 11..14 -> "файлов"
        n % 10 == 1 -> "файл"
        n % 10 in 2..4 -> "файла"
        else -> "файлов"
    }

@Composable
fun ReferenceSwitch(on: Boolean) {
    val thumb by
        androidx.compose.animation.core.animateDpAsState(
            if (on) 21.dp else 3.dp,
            tween(200),
            label = "referenceSwitchThumb",
        )
    val color by
        androidx.compose.animation.animateColorAsState(
            if (on) Blue else Color(0xff363c4a),
            tween(200),
            label = "referenceSwitchTrack",
        )
    Box(Modifier.size(42.dp, 24.dp).clip(RoundedCornerShape(12.dp)).background(color)) {
        Box(
            Modifier.padding(start = thumb, top = 3.dp)
                .size(18.dp)
                .clip(RoundedCornerShape(9.dp))
                .background(Color.White)
        )
    }
}

@Composable
fun FileTypeIcon(category: String) {
    val color = categoryColor(category)
    val opacity =
        if (category == "Архивы") .16f
        else if (category in listOf("Аудио", "Прочее")) .13f else .14f
    Box(
        Modifier.size(46.dp)
            .clip(RoundedCornerShape(15.dp))
            .background(color.copy(alpha = opacity)),
        contentAlignment = androidx.compose.ui.Alignment.Center,
    ) {
        IconSvg(
            when (category) {
                "Образы" -> 35
                "Архивы" -> 36
                "Видео" -> 37
                "Аудио" -> 38
                else -> 39
            },
            23,
            color,
        )
    }
}

@Composable
fun SettingSubtitle(text: String) {
    // A <small> after <br> still shares the 17px parent line box in the reference.
    Text(
        text,
        color = Muted,
        fontSize = 14.sp,
        lineHeight = 20.sp,
        letterSpacing = 0.sp,
        style =
            androidx.compose.ui.text.TextStyle(
                platformStyle =
                    androidx.compose.ui.text.PlatformTextStyle(includeFontPadding = false)
            ),
    )
}

fun Modifier.referenceHorizontalFade(): Modifier =
    graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
        .drawWithContent {
            drawContent()
            if (size.width > 0)
                drawRect(
                    Brush.horizontalGradient(
                        0f to Color.Black,
                        (1f - 28.dp.toPx() / size.width).coerceIn(0f, 1f) to Color.Black,
                        1f to Color.Transparent,
                    ),
                    blendMode = BlendMode.DstIn,
                )
        }

fun referenceLineHeight(size: Int): androidx.compose.ui.unit.TextUnit =
    when (size) {
        12 -> 14.sp
        13 -> 15.sp
        14 -> 16.sp
        15 -> 18.sp
        16 -> 19.sp
        17 -> 20.sp
        18 -> 21.sp
        19 -> 23.sp
        20 -> 23.sp
        21 -> 24.sp
        28 -> 28.sp
        29 -> 34.8.sp
        34 -> 34.sp
        else -> (size * 1.171875).sp
    }

fun Modifier.referenceTap(onClick: () -> Unit): Modifier = composed {
    val interaction = remember { MutableInteractionSource() }
    clickable(interactionSource = interaction, indication = null, onClick = onClick)
}
