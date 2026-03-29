import { getSession, getUser, onAuthStateChange, signOut } from "./auth.js";

export async function requireAuth(redirectTo = "/login") {
  const { data: session } = await getSession();
  if (!session) {
    window.location.href = redirectTo;
    return null;
  }
  return session;
}

export async function getCurrentUser() {
  const { data: session } = await getSession();
  if (session?.user) {
    return session.user;
  }

  const { data: user } = await getUser();
  return user;
}

export async function syncHeaderAuth() {
  const loginLink = document.getElementById("nav-login-link");
  const registerLink = document.getElementById("nav-register-link");
  const profileLink = document.getElementById("nav-profile-link");
  const logoutButton = document.getElementById("nav-logout-button");
  const ctaLink = document.getElementById("nav-cta-link");
  const { data: session } = await getSession();

  if (session?.user) {
    loginLink?.classList.add("hidden");
    registerLink?.classList.add("hidden");
    profileLink?.classList.remove("hidden");
    logoutButton?.classList.remove("hidden");
    if (ctaLink) {
      ctaLink.href = "/profile";
      ctaLink.textContent = "Профиль";
    }
  } else {
    loginLink?.classList.remove("hidden");
    registerLink?.classList.remove("hidden");
    profileLink?.classList.add("hidden");
    logoutButton?.classList.add("hidden");
    if (ctaLink) {
      ctaLink.href = "/chat";
      ctaLink.textContent = "Начать подбор";
    }
  }
}

export function bindLogoutButtons(selector = "[data-auth-logout]") {
  document.querySelectorAll(selector).forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      const { error } = await signOut();
      if (error) {
        window.alert(error.message);
        return;
      }
      window.location.href = "/";
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  await syncHeaderAuth();
  bindLogoutButtons();
  onAuthStateChange(async () => {
    await syncHeaderAuth();
  });
});
