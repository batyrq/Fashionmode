let cachedHealth = null;

export async function getHealthStatus(force = false) {
  if (cachedHealth && !force) {
    return cachedHealth;
  }

  const response = await fetch("/api/health", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Не удалось получить статус демо-сборки.");
  }

  cachedHealth = await response.json();
  return cachedHealth;
}

export function setInlineMessage(element, text, type = "error") {
  if (!element) {
    return;
  }

  const variants = {
    success: "bg-green-100 text-green-800 border border-green-200",
    info: "bg-blue-100 text-blue-800 border border-blue-200",
    warning: "bg-amber-100 text-amber-800 border border-amber-200",
    error: "bg-red-100 text-red-800 border border-red-200",
  };

  element.textContent = text;
  element.className = `mb-6 text-sm rounded-md px-3 py-2 ${variants[type] || variants.error}`;
  element.classList.remove("hidden");
}

export function mapFriendlyError(errorLike, fallbackText) {
  const raw = typeof errorLike === "string" ? errorLike : errorLike?.message || "";
  const text = raw.toLowerCase();

  if (!raw) {
    return fallbackText;
  }

  if (text.includes("auth_required")) {
    return "Войдите в аккаунт, чтобы сохранять товары в избранное.";
  }

  if (text.includes("admin access is required")) {
    return "Это действие доступно только администраторам каталога.";
  }

  if (text.includes("authenticated profile access is required") || text.includes("does not have a profile row")) {
    return "Для этого действия нужен корректный профиль Supabase. Проверьте вход в аккаунт.";
  }

  if (text.includes("measurement model") || text.includes("pose_model_path") || text.includes("seg_model_path")) {
    return "Модели для расчета мерок пока не установлены на этом компьютере.";
  }

  if (text.includes("image search")) {
    return "Поиск по фото недоступен в этой демо-сборке.";
  }

  if (text.includes("mediapipe") || text.includes("body analyzer runtime")) {
    return "Анализ фигуры пока недоступен в этой локальной сборке.";
  }

  if (text.includes("qwen runtime") || text.includes("torch") || text.includes("transformers")) {
    return "Стилист работает в быстром режиме рекомендаций без полной модели.";
  }

  if (text.includes("invalid login credentials")) {
    return "Не удалось войти. Проверьте email и пароль.";
  }

  if (text.includes("email not confirmed")) {
    return "Почта ещё не подтверждена. Для демо используйте заранее подтвержденный аккаунт или отключите email confirmation в demo-проекте Supabase.";
  }

  if (text.includes("user already registered")) {
    return "Пользователь с таким email уже зарегистрирован.";
  }

  if (text.includes("saved_outfits") || text.includes("row-level security") || text.includes("permission denied")) {
    return "Не удалось сохранить данные профиля в Supabase. Проверьте вход в аккаунт и настройки проекта.";
  }

  if (text.includes("claid")) {
    return "Виртуальная примерка сейчас недоступна. Попробуйте ещё раз через минуту.";
  }

  return raw || fallbackText;
}

export function describeChatMode(mode) {
  if (mode === "full") {
    return {
      label: "Полный режим",
      tone: "success",
      description: "Стилист использует полную модель.",
    };
  }

  return {
    label: "Быстрый режим",
    tone: "warning",
    description: "Стилист работает на быстром fallback-режиме рекомендаций.",
  };
}

export function capabilityPill(label, enabled, detail) {
  return `
    <div class="rounded-full border px-3 py-1.5 text-xs ${enabled ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800"}">
      <span class="font-semibold">${label}</span>
      <span class="ml-1 opacity-80">${detail}</span>
    </div>
  `;
}
