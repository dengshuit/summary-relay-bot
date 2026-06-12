import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Search, Check, X } from 'lucide-react';

export interface SelectOption {
  value: string;
  label: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  group?: string;
}

interface CustomSelectProps {
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  searchable?: boolean;
  className?: string;
  disabled?: boolean;
}

export default function CustomSelect({
  options,
  value,
  onChange,
  placeholder = '请选择',
  searchable = false,
  className = '',
  disabled = false,
}: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
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

  // Sync / Reset search query when dropdown opens / closes
  useEffect(() => {
    if (!isOpen) {
      setSearchQuery('');
    }
  }, [isOpen]);

  const selectedOption = options.find((opt) => opt.value === value);

  // Filter options based on search query
  const filteredOptions = options.filter((opt) =>
    opt.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
    opt.value.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group filtered options if group fields are used
  const groups: { [key: string]: SelectOption[] } = {};
  const ungrouped: SelectOption[] = [];

  filteredOptions.forEach((opt) => {
    if (opt.group) {
      if (!groups[opt.group]) {
        groups[opt.group] = [];
      }
      groups[opt.group].push(opt);
    } else {
      ungrouped.push(opt);
    }
  });

  const handleSelect = (val: string) => {
    onChange(val);
    setIsOpen(false);
  };

  return (
    <div
      className={`relative inline-block w-full font-sans text-xs ${className} ${
        disabled ? 'opacity-60 cursor-not-allowed' : ''
      }`}
      ref={containerRef}
    >
      {/* Trigger Button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full flex items-center justify-between gap-2 px-3 py-1.5 bg-white border border-[#e4e6ec] rounded-lg text-left text-gray-750 transition-all duration-150 h-[34px] font-medium ${
          disabled
            ? 'bg-gray-50/70 border-gray-100 cursor-not-allowed text-gray-400'
            : isOpen
            ? 'border-indigo-500 ring-2 ring-indigo-50 text-gray-900 shadow-xs'
            : 'hover:border-gray-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100'
        }`}
      >
        <span className="flex items-center gap-1.5 truncate flex-1 justify-between mr-1">
          <span className="flex items-center gap-1.5 truncate">
            {selectedOption?.icon && <span className="shrink-0">{selectedOption.icon}</span>}
            <span className="truncate">{selectedOption ? selectedOption.label : placeholder}</span>
          </span>
          {selectedOption?.badge && <span className="shrink-0">{selectedOption.badge}</span>}
        </span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-gray-400 shrink-0 transition-transform duration-150 ${
            isOpen ? 'transform rotate-180 text-indigo-500' : ''
          }`}
        />
      </button>

      {/* Styled Options Dropdown Panel */}
      {isOpen && (
        <div className="absolute left-0 right-0 mt-1.5 bg-white border border-[#e4e6ec] rounded-xl shadow-xl z-50 overflow-hidden flex flex-col max-h-[300px] animate-in fade-in duration-100">
          {/* Search bar inside Dropdown if searchable */}
          {searchable && (
            <div className="p-2 border-b border-[#f0f1f4] flex items-center gap-1.5 bg-[#fafbfd] shrink-0">
              <Search className="w-3.5 h-3.5 text-gray-450 ml-1.5 shrink-0" />
              <input
                type="text"
                placeholder="搜索选项"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-transparent border-none text-xs text-slate-800 focus:outline-none placeholder:text-gray-450 h-6 font-medium"
                onClick={(e) => e.stopPropagation()}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="p-0.5 rounded-full hover:bg-gray-200 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          )}

          {/* Options List Container */}
          <div className="flex-1 overflow-y-auto py-1 scrollbar-thin max-h-56">
            {filteredOptions.length === 0 ? (
              <div className="px-3 py-4 text-center text-[11px] text-gray-400 select-none">
                未搜索到匹配项
              </div>
            ) : (
              <>
                {/* Render Ungrouped options first */}
                {ungrouped.map((opt) => {
                  const isSelected = opt.value === value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => handleSelect(opt.value)}
                      className={`w-full text-left px-3 py-2 flex items-center justify-between gap-2.5 transition-colors cursor-pointer text-xs font-semibold ${
                        isSelected
                          ? 'bg-indigo-50/70 text-indigo-600'
                          : 'text-gray-700 hover:bg-slate-50 hover:text-gray-900'
                      }`}
                    >
                      <span className="flex items-center gap-1.5 truncate flex-1 justify-between">
                        <span className="flex items-center gap-1.5 truncate">
                          {opt.icon && <span className="shrink-0">{opt.icon}</span>}
                          <span className="truncate">{opt.label}</span>
                        </span>
                        {opt.badge && <span className="shrink-0">{opt.badge}</span>}
                      </span>
                      {isSelected && (
                        <Check className="w-3.5 h-3.5 text-indigo-500 stroke-[3.5] shrink-0 ml-1" />
                      )}
                    </button>
                  );
                })}

                {/* Render Grouped options */}
                {Object.entries(groups).map(([groupName, groupOpts]) => (
                  <div key={groupName} className="border-t border-[#f0f1f4]/75 first:border-0 mt-1 pt-1">
                    <span className="text-[10px] font-bold text-gray-400 px-3 py-1 uppercase tracking-wider block bg-slate-50/40 select-none">
                      {groupName}
                    </span>
                    {groupOpts.map((opt) => {
                      const isSelected = opt.value === value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => handleSelect(opt.value)}
                          className={`w-full text-left px-4 py-1.5 flex items-center justify-between gap-2.5 transition-colors cursor-pointer text-xs font-medium ${
                            isSelected
                              ? 'bg-indigo-50/70 text-indigo-600'
                              : 'text-gray-650 hover:bg-slate-50 hover:text-gray-900'
                          }`}
                        >
                          <span className="flex items-center gap-1.5 truncate flex-1 justify-between">
                            <span className="flex items-center gap-1.5 truncate">
                              {opt.icon && <span className="shrink-0">{opt.icon}</span>}
                              <span className="truncate">{opt.label}</span>
                            </span>
                            {opt.badge && <span className="shrink-0">{opt.badge}</span>}
                          </span>
                          {isSelected && (
                            <Check className="w-3.5 h-3.5 text-indigo-500 stroke-[3.5] shrink-0 ml-1" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
