"use client"

import * as React from "react"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { DayPicker } from "react-day-picker"

import { cn } from "@/lib/utils"

export type CalendarProps = React.ComponentProps<typeof DayPicker>

function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  ...props
}: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("p-3 bg-white rounded-md", className)}
      classNames={{
        months: "flex flex-col sm:flex-row space-y-4 sm:space-x-4 sm:space-y-0",
        month: "space-y-4",
        month_caption: "flex justify-center pt-1 relative items-center mb-2 text-sm font-bold text-slate-800",
        nav: "space-x-1 flex items-center",
        button_previous: cn(
          "h-7 w-7 bg-transparent border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-md p-0 opacity-70 hover:opacity-100 transition-all flex items-center justify-center absolute left-1"
        ),
        button_next: cn(
          "h-7 w-7 bg-transparent border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-md p-0 opacity-70 hover:opacity-100 transition-all flex items-center justify-center absolute right-1"
        ),
        month_grid: "w-full border-collapse space-y-1",
        weekdays: "flex",
        weekday: "text-slate-400 rounded-md w-9 font-bold text-[11px] uppercase tracking-wider text-center",
        week: "flex w-full mt-1.5",
        day: "h-9 w-9 p-0 font-medium text-slate-800 rounded-md hover:bg-slate-100 flex items-center justify-center transition-all cursor-pointer",
        selected: "bg-indigo-600 text-white hover:bg-indigo-700 hover:text-white focus:bg-indigo-600 focus:text-white font-bold shadow-xs",
        today: "border border-indigo-250 text-indigo-700 font-bold",
        outside: "text-slate-350 opacity-40 hover:bg-slate-50",
        disabled: "text-slate-300 opacity-20 cursor-not-allowed hover:bg-transparent",
        hidden: "invisible",
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation }) => {
          if (orientation === "left") {
            return <ChevronLeft className="h-4 w-4 text-slate-650" />
          }
          return <ChevronRight className="h-4 w-4 text-slate-650" />
        }
      }}
      {...props}
    />
  )
}
Calendar.displayName = "Calendar"

export { Calendar }
