import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'

import { applyTheme, getStoredThemePreference, isDarkThemeActive, setStoredThemePreference } from '@/lib/theme'
import { Button } from './ui/button'

export function ToggleTheme() {
  const [isDark, setIsDark] = useState<boolean>(() => {
    return isDarkThemeActive(getStoredThemePreference())
  })

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = () => {
      if (getStoredThemePreference() === 'system') {
        setIsDark(media.matches)
      }
    }

    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  function handleToggleTheme() {
    const nextTheme = isDark ? 'light' : 'dark'
    setStoredThemePreference(nextTheme)
    applyTheme(nextTheme)
    setIsDark(nextTheme === 'dark')
  }

  return (
    <Button
      type="button"
      onClick={handleToggleTheme}
      variant="secondary"
      className="cursor-pointer rounded-full"
      size="icon"
      //   className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background text-foreground hover:bg-accent hover:text-accent-foreground"
      aria-label={isDark ? 'Ativar tema claro' : 'Ativar tema escuro'}
      title={isDark ? 'Ativar tema claro' : 'Ativar tema escuro'}
    >
      {isDark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  )
}
