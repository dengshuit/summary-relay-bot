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
      <div className="fixed bottom-4 right-4 z-[100] flex w-[calc(100vw-2rem)] max-w-[360px] flex-col gap-2 pointer-events-none sm:bottom-6 sm:right-6">
        <AnimatePresence initial={false}>
          {toasts.map((toast) => {
            const Icon = toneIcon[toast.tone];

            return (
              <motion.div
                key={toast.id}
                role={toast.tone === 'error' ? 'alert' : 'status'}
                initial={{ opacity: 0, y: 8, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 6, scale: 0.98 }}
                transition={{ duration: 0.14, ease: 'easeOut' }}
                className="pointer-events-auto rounded-md border border-[#d9dde5] bg-[#fbfbfa] px-3 py-2.5 text-gray-900 shadow-[0_1px_2px_rgba(15,23,42,0.06)]"
              >
                <div className="flex items-start gap-2.5">
                  <Icon className="mt-0.5 h-4 w-4 shrink-0 text-gray-500" strokeWidth={2} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-semibold leading-5 text-gray-950">{toast.title}</p>
                    {toast.detail && (
                      <p className="mt-0.5 text-[11px] leading-4 text-gray-600 break-words">{toast.detail}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    aria-label="关闭提示"
                    onClick={() => removeToast(toast.id)}
                    className="-mr-1 rounded p-0.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
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
