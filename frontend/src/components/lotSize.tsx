import { forwardRef, useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'
import { Button } from './ui/button'
import { ArrowBigDownDash, ArrowBigUpDash } from 'lucide-react'

type LotSizeProps = Omit<React.ComponentPropsWithoutRef<'input'>, 'type' | 'value' | 'defaultValue' | 'onChange' | 'min' | 'step'> & {
  value?: number
  defaultValue?: number
  min?: number
  step?: number
  className?: string
  onValueChange?: (nextValue: number) => void
}

export const LotSize = forwardRef<HTMLInputElement, LotSizeProps>(function LotSize(
  { value, defaultValue = 0.01, min = 0.01, step = 0.01, className, name, disabled, onValueChange, ...inputProps },
  ref
) {
  const isControlled = value !== undefined
  const stepPrecision = getStepPrecision(step)
  const stepFactor = 10 ** stepPrecision
  const displayPrecision = Math.max(2, stepPrecision)

  const holdTimeoutRef = useRef<number | null>(null)
  const holdIntervalRef = useRef<number | null>(null)
  const [internalValue, setInternalValue] = useState<number>(normalizeLotValue(defaultValue, min, stepFactor))

  const currentValue = isControlled ? normalizeLotValue(value, min, stepFactor) : internalValue

  const currentValueRef = useRef<number>(currentValue)

  useEffect(() => {
    currentValueRef.current = currentValue
  }, [currentValue])

  function adjustValue(delta: number) {
    if (disabled) {
      return
    }

    const next = normalizeLotValue(currentValueRef.current + delta, min, stepFactor)
    currentValueRef.current = next

    if (!isControlled) {
      setInternalValue(next)
    }

    onValueChange?.(next)
  }

  function stopHold() {
    if (holdTimeoutRef.current !== null) {
      window.clearTimeout(holdTimeoutRef.current)
      holdTimeoutRef.current = null
    }

    if (holdIntervalRef.current !== null) {
      window.clearInterval(holdIntervalRef.current)
      holdIntervalRef.current = null
    }
  }

  function startHold(delta: number) {
    if (disabled) {
      return
    }

    adjustValue(delta)
    stopHold()

    holdTimeoutRef.current = window.setTimeout(() => {
      holdIntervalRef.current = window.setInterval(() => {
        adjustValue(delta)
      }, 90)
    }, 300)
  }

  function handleKeyAdjust(event: React.KeyboardEvent<HTMLButtonElement>, delta: number) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      adjustValue(delta)
    }
  }

  useEffect(() => {
    return () => stopHold()
  }, [])

  return (
    <div className={cn('border-border bg-background flex h-8 w-full overflow-hidden rounded-xs border', className)}>
      <div className="flex w-32 items-center justify-center bg-blue-500 p-2 text-xs text-blue-200">
        <ArrowBigUpDash />
      </div>

      <Button
        type="button"
        variant="secondary"
        disabled={disabled}
        onPointerDown={() => startHold(-step)}
        onPointerUp={stopHold}
        onPointerLeave={stopHold}
        onPointerCancel={stopHold}
        onKeyDown={event => handleKeyAdjust(event, -step)}
        className="h-full cursor-pointer rounded-xs"
        aria-label="Diminuir lote"
      >
        ▼
      </Button>

      <div className="bg-secondary/30 text-foreground grid h-full w-full place-items-center px-2 text-sm font-medium tabular-nums">{currentValue.toFixed(displayPrecision)}</div>

      <Button
        type="button"
        variant="secondary"
        disabled={disabled}
        onPointerDown={() => startHold(step)}
        onPointerUp={stopHold}
        onPointerLeave={stopHold}
        onPointerCancel={stopHold}
        onKeyDown={event => handleKeyAdjust(event, step)}
        className="h-full cursor-pointer rounded-xs"
        aria-label="Aumentar lote"
      >
        ▲
      </Button>

      <div className="flex w-32 items-center justify-center bg-red-500 p-2 text-xs text-red-200">
        <ArrowBigDownDash />
      </div>

      <input {...inputProps} ref={ref} name={name} type="hidden" value={currentValue} readOnly />
    </div>
  )
})

function normalizeLotValue(raw: number, min: number, stepFactor: number): number {
  const clamped = Math.max(raw, min)
  return Math.round(clamped * stepFactor) / stepFactor
}

function getStepPrecision(stepValue: number): number {
  const text = stepValue.toString()
  if (!text.includes('.')) {
    return 0
  }
  return text.split('.')[1].length
}
