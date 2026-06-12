import React, { useState, useRef, useEffect } from 'react';
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, X } from 'lucide-react';

interface DateRangePickerProps {
  fromDate: string;
  toDate: string;
  onChange: (from: string, to: string) => void;
}

export default function DateRangePicker({ fromDate, toDate, onChange }: DateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Calendar view state (displays year & month)
  const [viewDate, setViewDate] = useState(() => {
    const d = fromDate ? new Date(fromDate) : new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });

  // Temporarily hold selections in popover before confirming
  const [tempFrom, setTempFrom] = useState(fromDate);
  const [tempTo, setTempTo] = useState(toDate);

  // Keep temporary sync when prop updates
  useEffect(() => {
    setTempFrom(fromDate);
    setTempTo(toDate);
    if (fromDate) {
      const d = new Date(fromDate);
      setViewDate(new Date(d.getFullYear(), d.getMonth(), 1));
    }
  }, [fromDate, toDate]);

  // Click outside listener to close dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const formatLocal = (d: Date) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const r = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${r}`;
  };

  // Presets definition
  const presets = [
    { label: '今天', getValue: () => { const d = new Date(); return { from: formatLocal(d), to: formatLocal(d) }; } },
    { label: '昨天', getValue: () => { const d = new Date(); d.setDate(d.getDate() - 1); const s = formatLocal(d); return { from: s, to: s }; } },
    { label: '近 7 天', getValue: () => { const end = new Date(); const s = new Date(); s.setDate(s.getDate() - 6); return { from: formatLocal(s), to: formatLocal(end) }; } },
    { label: '近 30 天', getValue: () => { const end = new Date(); const s = new Date(); s.setDate(s.getDate() - 29); return { from: formatLocal(s), to: formatLocal(end) }; } },
    { label: '本月', getValue: () => { const s = new Date(); s.setDate(1); return { from: formatLocal(s), to: formatLocal(new Date()) }; } },
  ];

  const handleApplyPreset = (getVal: () => { from: string, to: string }) => {
    const { from, to } = getVal();
    setTempFrom(from);
    setTempTo(to);
    onChange(from, to);
    setIsOpen(false);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setTempFrom('');
    setTempTo('');
    onChange('', '');
    setIsOpen(false);
  };

  // Calendar Calculations
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();

  const getDaysInMonth = (y: number, m: number) => new Date(y, m + 1, 0).getDate();
  const getFirstDayOfMonth = (y: number, m: number) => {
    const d = new Date(y, m, 1).getDay();
    return d === 0 ? 6 : d - 1; // Map Sunday (0) to index 6, Monday (1) to index 0
  };

  const daysInMonth = getDaysInMonth(year, month);
  const firstDayIndex = getFirstDayOfMonth(year, month);

  const prevMonthDays = getDaysInMonth(month === 0 ? year - 1 : year, month === 0 ? 11 : month - 1);

  // Array representing the grids of days
  const calendarCells = [];

  // Muted filler padding from previous month
  for (let i = firstDayIndex - 1; i >= 0; i--) {
    const prevYear = month === 0 ? year - 1 : year;
    const prevMon = month === 0 ? 11 : month - 1;
    const prevDayVal = prevMonthDays - i;
    const dateStr = `${prevYear}-${String(prevMon + 1).padStart(2, '0')}-${String(prevDayVal).padStart(2, '0')}`;
    calendarCells.push({ day: prevDayVal, isCurrentMonth: false, dateStr });
  }

  // Days in current month
  for (let i = 1; i <= daysInMonth; i++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
    calendarCells.push({ day: i, isCurrentMonth: true, dateStr });
  }

  // Next months padding to fill 42 boxes (6 rows * 7 columns)
  const remainingBoxes = 42 - calendarCells.length;
  for (let i = 1; i <= remainingBoxes; i++) {
    const nextYear = month === 11 ? year + 1 : year;
    const nextMon = month === 11 ? 0 : month + 1;
    const dateStr = `${nextYear}-${String(nextMon + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
    calendarCells.push({ day: i, isCurrentMonth: false, dateStr });
  }

  const handleDaySelect = (dateStr: string) => {
    if (!tempFrom || (tempFrom && tempTo)) {
      setTempFrom(dateStr);
      setTempTo('');
    } else {
      if (dateStr < tempFrom) {
        setTempFrom(dateStr);
        setTempTo('');
      } else {
        setTempTo(dateStr);
      }
    }
  };

  const handleConfirm = () => {
    onChange(tempFrom, tempTo || tempFrom);
    setIsOpen(false);
  };

  const changeMonth = (direction: number) => {
    setViewDate(new Date(year, month + direction, 1));
  };

  // Helper helper validation display label
  const getDisplayLabel = () => {
    if (!fromDate) return '选择日期范围';
    if (!toDate) return `${fromDate} 起`;
    if (fromDate === toDate) return fromDate;
    return `${fromDate} 至 ${toDate}`;
  };

  return (
    <div className="relative inline-block text-left font-sans" ref={containerRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2.5 px-3.5 py-1.5 bg-white border border-[#e4e6ec] rounded-lg hover:border-gray-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 transition-all duration-150 h-[34px] cursor-pointer text-xs font-semibold text-gray-700 min-w-[140px]"
      >
        <CalendarIcon className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
        <span className="flex-1 text-left truncate">{getDisplayLabel()}</span>
        {fromDate && (
          <span
            onClick={handleClear}
            className="p-0.5 rounded-full hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors shrink-0 ml-1"
          >
            <X className="w-3 h-3" />
          </span>
        )}
      </button>

      {/* Styled Semi Design Style DatePicker Dropdown Panel */}
      {isOpen && (
        <div className="absolute right-0 mt-1.5 w-[520px] bg-white rounded-2xl border border-[#e4e6ec] shadow-xl z-55 flex overflow-hidden animate-in fade-in duration-150">
          {/* Quick Presets Left Rail */}
          <div className="w-[120px] border-r border-[#f0f1f4] bg-[#fafbfd] p-2 flex flex-col gap-1 shrink-0">
            <span className="text-[10px] font-bold text-gray-400 px-2 py-1 uppercase tracking-wider">
              快捷选择
            </span>
            {presets.map((p) => {
              const isActive = tempFrom && tempTo &&
                tempFrom === p.getValue().from &&
                tempTo === p.getValue().to;
              return (
                <button
                  key={p.label}
                  type="button"
                  onClick={() => handleApplyPreset(p.getValue)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-600'
                      : 'text-gray-600 hover:bg-gray-100/70 hover:text-gray-900'
                  }`}
                >
                  {p.label}
                </button>
              );
            })}
            <div className="flex-1" />
            <button
              type="button"
              onClick={() => {
                setTempFrom('');
                setTempTo('');
                onChange('', '');
                setIsOpen(false);
              }}
              className="text-center w-full px-2 py-1.5 text-xs text-rose-500 hover:bg-rose-50 rounded-lg font-semibold transition-all mt-auto"
            >
              清空范围
            </button>
          </div>

          {/* Interactive Month Picker Panel */}
          <div className="flex-1 flex flex-col p-4">
            {/* Header controls */}
            <div className="flex items-center justify-between pb-3 border-b border-[#f0f1f4] mb-3">
              <button
                type="button"
                onClick={() => changeMonth(-1)}
                className="p-1 rounded-md text-gray-400 hover:bg-gray-100/75 hover:text-gray-700 cursor-pointer"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <h4 className="text-xs font-bold text-gray-900 font-mono">
                {year}年 {month + 1}月
              </h4>
              <button
                type="button"
                onClick={() => changeMonth(1)}
                className="p-1 rounded-md text-gray-400 hover:bg-gray-100/75 hover:text-gray-700 cursor-pointer"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* Weeks titles */}
            <div className="grid grid-cols-7 gap-y-1 mb-1 text-center">
              {['一', '二', '三', '四', '五', '六', '日'].map((w, index) => (
                <span key={index} className="text-[10px] font-bold text-gray-400 uppercase">
                  {w}
                </span>
              ))}
            </div>

            {/* Calendar Days grids */}
            <div className="grid grid-cols-7 gap-y-1 text-center font-mono text-xs">
              {calendarCells.map((cell, idx) => {
                const isSelectedStart = tempFrom === cell.dateStr;
                const isSelectedEnd = tempTo === cell.dateStr;
                const isSelecting = tempFrom && !tempTo && tempFrom === cell.dateStr;
                const isMiddle = tempFrom && tempTo && cell.dateStr > tempFrom && cell.dateStr < tempTo;

                let dayBgClass = 'hover:bg-gray-100 text-gray-700 rounded-lg';
                if (!cell.isCurrentMonth) {
                  dayBgClass = 'text-gray-300 hover:bg-gray-50';
                }

                if (isSelectedStart || isSelectedEnd || isSelecting) {
                  dayBgClass = 'bg-indigo-600 text-white rounded-full font-bold shadow-sm z-10';
                } else if (isMiddle) {
                  dayBgClass = 'bg-indigo-50 text-indigo-700 rounded-none font-medium';
                }

                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleDaySelect(cell.dateStr)}
                    className={`w-8 h-8 flex items-center justify-center transition-all cursor-pointer relative ${dayBgClass}`}
                  >
                    {/* Add subtle side pill connectors for spanning range nicely */}
                    {isMiddle && (
                      <div className="absolute inset-y-0 -left-1 -right-1 bg-indigo-50/70 -z-10" />
                    )}
                    {isSelectedStart && tempTo && (
                      <div className="absolute inset-y-0 right-0 w-4 bg-indigo-50/70 -z-10" />
                    )}
                    {isSelectedEnd && tempFrom && (
                      <div className="absolute inset-y-0 left-0 w-4 bg-indigo-50/70 -z-10" />
                    )}
                    <span className="relative z-10">{cell.day}</span>
                  </button>
                );
              })}
            </div>

            {/* Bottom confirmation footer layout */}
            <div className="mt-4 pt-3 border-t border-[#f0f1f4] flex justify-between items-center gap-4">
              <div className="text-[10px] text-gray-400">
                {tempFrom ? (
                  <span>
                    已选择:{' '}
                    <strong className="text-indigo-600 underline font-mono">
                      {tempFrom}
                    </strong>{' '}
                    {tempTo && (
                      <>
                        至{' '}
                        <strong className="text-indigo-600 underline font-mono">
                          {tempTo}
                        </strong>
                      </>
                    )}
                  </span>
                ) : (
                  <span>未指定范围</span>
                )}
              </div>
              <div className="flex gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="px-3 py-1.5 border border-gray-100 rounded-lg text-gray-500 text-[10px] hover:bg-gray-50 font-bold transition-all cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={handleConfirm}
                  disabled={!tempFrom}
                  className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-[10px] font-bold shadow-sm disabled:opacity-50 transition-all cursor-pointer"
                >
                  确定
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
