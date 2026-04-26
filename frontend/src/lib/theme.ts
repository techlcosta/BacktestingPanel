export type ThemePreference = 'light' | 'dark' | 'system'

const THEME_STORAGE_KEY = 'theme-preference'

function getSystemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function getStoredThemePreference(): ThemePreference {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
  if (stored === 'light' || stored === 'dark' || stored === 'system') {
    return stored
  }
  return 'system'
}

export function setStoredThemePreference(theme: ThemePreference): void {
  window.localStorage.setItem(THEME_STORAGE_KEY, theme)
}

export function isDarkThemeActive(theme: ThemePreference): boolean {
  if (theme === 'system') {
    return getSystemPrefersDark()
  }
  return theme === 'dark'
}

export function applyTheme(theme: ThemePreference): void {
  const isDark = isDarkThemeActive(theme)
  document.documentElement.classList.toggle('dark', isDark)
  document.documentElement.style.colorScheme = isDark ? 'dark' : 'light'
}

export function setupTheme(): void {
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  applyTheme(getStoredThemePreference())

  media.addEventListener('change', () => {
    if (getStoredThemePreference() === 'system') {
      applyTheme('system')
    }
  })
}
