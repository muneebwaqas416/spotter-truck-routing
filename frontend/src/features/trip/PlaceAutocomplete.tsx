import {
  Combobox,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
  Field,
  Label,
} from '@headlessui/react'
import { skipToken } from '@reduxjs/toolkit/query'
import { MapPin, X } from 'lucide-react'
import { useId } from 'react'

import { InputIcon } from '@/components/InputIcon'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label as UiLabel } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useGeocodeQuery } from '@/redux/api'

import { FieldError } from './FieldError'
import { cn } from '@/lib/utils'

const MIN_QUERY_LENGTH = 3

interface PlaceAutocompleteProps {
  label: string
  value: string
  onChange: (value: string) => void
  onBlur: () => void
  error?: string
  disabled?: boolean
  dotClassName: string
}

/** Free text is allowed; suggestions help pick a precise place. Headless UI handles a11y and keyboard. */
export function PlaceAutocomplete({
  label,
  value,
  onChange,
  onBlur,
  error,
  disabled,
  dotClassName,
}: PlaceAutocompleteProps) {
  const errorId = useId()
  const query = useDebouncedValue(value.trim(), 300)
  const shouldSearch = query.length >= MIN_QUERY_LENGTH
  const {
    data: suggestions = [],
    isFetching,
    isError,
  } = useGeocodeQuery(shouldSearch ? query : skipToken)

  return (
    <Field disabled={disabled} className="space-y-1.5">
      <Label as={UiLabel}>
        <span aria-hidden className={cn('size-2 rounded-full', dotClassName)} />
        {label}
      </Label>

      <Combobox value={value} onChange={(selected: string | null) => onChange(selected ?? '')}>
        <div className="relative">
          <InputIcon icon={MapPin} />
          {/* Headless UI drives the combobox behaviour; shadcn's Input provides the look. */}
          <ComboboxInput
            as={Input}
            autoComplete="off"
            placeholder="City, address or place"
            displayValue={(place: string) => place}
            onChange={(event) => onChange(event.target.value)}
            onBlur={onBlur}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
            className="h-10 bg-white pr-9 pl-9"
          />
          {value && !disabled && (
            <Button
              variant="ghost"
              size="icon-xs"
              aria-label={`Clear ${label.toLowerCase()}`}
              onClick={() => onChange('')}
              className="absolute top-1/2 right-1.5 -translate-y-1/2 text-subtle"
            >
              <X />
            </Button>
          )}
        </div>

        {shouldSearch && (
          <ComboboxOptions
            anchor={{ to: 'bottom start', gap: 4 }}
            className="z-30 w-(--input-width) overflow-hidden rounded-lg border border-border bg-white text-sm shadow-lg empty:invisible"
          >
            {isFetching && suggestions.length === 0 && (
              <div className="flex items-center gap-2 px-3 py-2.5 text-muted-foreground">
                <Spinner /> Searching…
              </div>
            )}
            {isError && (
              <div className="px-3 py-2.5 text-muted-foreground">
                Suggestions unavailable — you can still type a full address.
              </div>
            )}
            {!isFetching && !isError && suggestions.length === 0 && (
              <div className="px-3 py-2.5 text-muted-foreground">
                No matches — try a city and state.
              </div>
            )}
            {suggestions.map((suggestion) => (
              <ComboboxOption
                key={suggestion.id}
                value={suggestion.label}
                className="flex cursor-pointer items-center gap-2 px-3 py-2.5 data-focus:bg-accent data-focus:text-accent-foreground"
              >
                <MapPin aria-hidden className="size-4 text-subtle" />
                {suggestion.label}
              </ComboboxOption>
            ))}
          </ComboboxOptions>
        )}
      </Combobox>

      <FieldError id={errorId} message={error} />
    </Field>
  )
}
