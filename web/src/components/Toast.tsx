import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  X
} from 'lucide-react';

export type ToastTone = 'success' | 'error' | 'warning' | 'info';

export interface ToastOptions {
  title: string;
  detail?: string;
  tone?: ToastTone;
  durationMs?: number;
}

interface ToastItem extends Required<Pick<ToastOptions, 'title' | 'tone' | 'durationMs'>> {
  id: number;
  detail?: string;
}

interface ToastContextValue {
  showToast: (options: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const toneIcon = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info
};

const toneStyle: Record<
  ToastTone,
  {
    accent: string;
    border: string;
    icon: string;
    iconFrame: string;
    progress: string;
  }
> = {
  success: {
    accent: 'bg-emerald-500',
    border: 'border-emerald-200/80',
    icon: 'text-emerald-600',
    iconFrame: 'bg-emerald-50 border-emerald-100',
    progress: 'bg-emerald-500'
  },
  error: {
    accent: 'bg-red-500',
    border: 'border-red-200/90',
    icon: 'text-red-600',
    iconFrame: 'bg-red-50 border-red-100',
    progress: 'bg-red-500'
  },
  warning: {
    accent: 'bg-amber-500',
    border: 'border-amber-200/90',
    icon: 'text-amber-600',
    iconFrame: 'bg-amber-50 border-amber-100',
    progress: 'bg-amber-500'
  },
  info: {
    accent: 'bg-indigo-500',
    border: 'border-indigo-200/80',
    icon: 'text-indigo-600',
    iconFrame: 'bg-indigo-50 border-indigo-100',
    progress: 'bg-indigo-500'
  }
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const timers = useRef<Map<number, number>>(new Map());

  const removeToast = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));

    const timer = timers.current.get(id);
    if (timer) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const showToast = useCallback((options: ToastOptions) => {
    const id = nextId.current;
    nextId.current += 1;

    const toast: ToastItem = {
      id,
      title: options.title,
      detail: options.detail,
      tone: options.tone || 'info',
      durationMs: options.durationMs ?? 3600
    };

    setToasts((current) => [...current, toast].slice(-4));

    const timer = window.setTimeout(() => removeToast(id), toast.durationMs);
    timers.current.set(id, timer);
  }, [removeToast]);

  useEffect(() => {
    return () => {
      timers.current.forEach((timer) => window.clearTimeout(timer));
      timers.current.clear();
    };
  }, []);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex w-[calc(100vw-2rem)] max-w-[388px] flex-col gap-2.5 pointer-events-none sm:bottom-6 sm:right-6">
        <AnimatePresence initial={false}>
          {toasts.map((toast) => {
            const Icon = toneIcon[toast.tone];
            const style = toneStyle[toast.tone];

            return (
              <motion.div
                key={toast.id}
                role={toast.tone === 'error' ? 'alert' : 'status'}
                initial={{ opacity: 0, x: 14, y: 8, scale: 0.98 }}
                animate={{ opacity: 1, x: 0, y: 0, scale: 1 }}
                exit={{ opacity: 0, x: 10, y: 6, scale: 0.98 }}
                transition={{ duration: 0.18, ease: 'easeOut' }}
                className={`pointer-events-auto relative overflow-hidden rounded-xl border ${style.border} bg-white text-gray-900 shadow-[0_14px_30px_rgba(31,35,41,0.12),0_2px_6px_rgba(31,35,41,0.06)]`}
              >
                <span className={`absolute inset-y-0 left-0 w-1 ${style.accent}`} aria-hidden="true" />
                <div className="flex items-start gap-3 px-3.5 py-3">
                  <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${style.iconFrame}`}>
                    <Icon className={`h-4.5 w-4.5 shrink-0 ${style.icon}`} strokeWidth={2.3} />
                  </div>
                  <div className="min-w-0 flex-1 pt-0.5">
                    <div className="mb-0.5 flex min-w-0 items-center">
                      <p className="min-w-0 truncate text-[13px] font-bold leading-5 text-gray-950">{toast.title}</p>
                    </div>
                    {toast.detail && (
                      <p className="text-[12px] leading-5 text-gray-600 break-words">{toast.detail}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    aria-label="关闭提示"
                    onClick={() => removeToast(toast.id)}
                    className="-mr-1 mt-0.5 rounded-md p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
                  >
                    <X className="h-3.5 w-3.5" strokeWidth={2.4} />
                  </button>
                </div>
                <motion.span
                  className={`absolute bottom-0 left-0 h-0.5 w-full origin-left ${style.progress}`}
                  initial={{ scaleX: 1 }}
                  animate={{ scaleX: 0 }}
                  transition={{ duration: toast.durationMs / 1000, ease: 'linear' }}
                  aria-hidden="true"
                />
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }

  return context.showToast;
}
