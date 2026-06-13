import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Eye,
  Loader2,
  RotateCcw,
  X,
  XCircle
} from 'lucide-react';

export type TaskProgressStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'canceled';
export type TaskProgressStep = 'submitted' | 'queued' | 'running' | 'generating' | 'completed';

interface TaskProgressPanelProps {
  status: TaskProgressStatus;
  step: TaskProgressStep;
  messageCount?: number | null;
  sequenceRange?: string | null;
  errorType?: string | null;
  errorMessage?: string | null;
  isLongRunning?: boolean;
  onRetry?: () => void;
  onCancel?: () => void;
  onViewResult?: () => void;
  onBackground?: () => void;
}

const taskSteps: Array<{ id: TaskProgressStep; label: string }> = [
  { id: 'submitted', label: '已提交' },
  { id: 'queued', label: '排队中' },
  { id: 'running', label: '执行中' },
  { id: 'generating', label: '生成结果' },
  { id: 'completed', label: '完成' }
];

const terminalStatuses = new Set<TaskProgressStatus>(['succeeded', 'failed', 'canceled']);

function stepIndex(step: TaskProgressStep): number {
  return Math.max(0, taskSteps.findIndex((item) => item.id === step));
}

function titleForStatus(status: TaskProgressStatus, step: TaskProgressStep): string {
  if (status === 'succeeded') return '生成结果已完成';
  if (status === 'failed') return '任务执行失败';
  if (status === 'canceled') return '任务已取消';
  if (step === 'generating') return '正在生成结果';
  return '正在执行任务';
}

export default function TaskProgressPanel({
  status,
  step,
  messageCount,
  sequenceRange,
  errorType,
  errorMessage,
  isLongRunning = false,
  onRetry,
  onCancel,
  onViewResult,
  onBackground
}: TaskProgressPanelProps) {
  const activeIndex = stepIndex(step);
  const isTerminal = terminalStatuses.has(status);
  const isFailed = status === 'failed';
  const isSucceeded = status === 'succeeded';
  const isCanceled = status === 'canceled';
  const accent = isFailed
    ? 'border-red-200 bg-red-50/70'
    : isSucceeded
      ? 'border-emerald-200 bg-emerald-50/70'
      : isCanceled
        ? 'border-gray-200 bg-gray-50'
        : 'border-blue-200 bg-white';

  return (
    <section className={`rounded-lg border ${accent} shadow-sm overflow-hidden`} aria-live="polite">
      <div className="px-4 py-3 border-b border-black/5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {isFailed ? (
              <XCircle className="h-4 w-4 text-red-600 shrink-0" />
            ) : isSucceeded ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            ) : isCanceled ? (
              <X className="h-4 w-4 text-gray-500 shrink-0" />
            ) : (
              <Loader2 className="h-4 w-4 text-blue-600 animate-spin shrink-0" />
            )}
            <h3 className="text-sm font-bold text-gray-900 truncate">{titleForStatus(status, step)}</h3>
          </div>
          <p className="text-xs text-gray-600 mt-1">
            {isLongRunning
              ? '仍在处理中，任务可能需要更长时间，你可以留在当前页面等待'
              : '任务可能需要 1-3 分钟，你可以留在当前页面等待'}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {!isTerminal && onBackground && (
            <button
              type="button"
              onClick={onBackground}
              className="px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-semibold text-gray-600 hover:bg-slate-50 hover:border-gray-300 transition-all cursor-pointer"
            >
              后台运行
            </button>
          )}
          {!isTerminal && onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-semibold text-gray-600 hover:bg-slate-50 hover:border-gray-300 transition-all cursor-pointer inline-flex items-center gap-1.5"
            >
              <X className="h-3.5 w-3.5" />
              取消
            </button>
          )}
          {isFailed && onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="px-3 py-1.5 rounded-lg bg-red-600 text-xs font-semibold text-white hover:bg-red-700 transition-all cursor-pointer inline-flex items-center gap-1.5"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              重试
            </button>
          )}
          {isSucceeded && onViewResult && (
            <button
              type="button"
              onClick={onViewResult}
              className="px-2.5 py-1.5 font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50/50 hover:bg-indigo-50 border border-indigo-100/80 rounded-lg cursor-pointer transition-all inline-flex items-center gap-1 shrink-0"
            >
              <Eye className="h-3.5 w-3.5" />
              查看结果
            </button>
          )}
        </div>
      </div>

      {!isTerminal && (
        <div className="h-1.5 bg-gray-100 overflow-hidden">
          <div className="task-progress-indeterminate h-full w-1/3 bg-blue-500" />
        </div>
      )}

      <div className="p-4 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(220px,280px)] gap-4">
        <ol className="grid grid-cols-1 sm:grid-cols-5 gap-2">
          {taskSteps.map((item, index) => {
            const done = isSucceeded || index < activeIndex;
            const current = !isTerminal && index === activeIndex;
            const failedHere = isFailed && index === activeIndex;
            const canceledHere = isCanceled && index === activeIndex;
            return (
              <li
                key={item.id}
                className={`min-h-[58px] rounded-md border px-3 py-2 flex items-center gap-2 ${
                  done
                    ? 'border-emerald-200 bg-white'
                    : current
                      ? 'border-blue-200 bg-blue-50'
                      : failedHere
                        ? 'border-red-200 bg-white'
                        : canceledHere
                          ? 'border-gray-200 bg-white'
                          : 'border-gray-200 bg-white/70'
                }`}
              >
                <span className="h-5 w-5 shrink-0 inline-flex items-center justify-center">
                  {done ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  ) : current ? (
                    <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
                  ) : failedHere ? (
                    <XCircle className="h-4 w-4 text-red-600" />
                  ) : canceledHere ? (
                    <X className="h-4 w-4 text-gray-500" />
                  ) : (
                    <Circle className="h-3.5 w-3.5 text-gray-300 fill-gray-200" />
                  )}
                </span>
                <span className={`text-xs font-semibold ${done || current ? 'text-gray-900' : 'text-gray-500'}`}>
                  {item.label}
                </span>
              </li>
            );
          })}
        </ol>

        <div className="rounded-md border border-gray-200 bg-white px-3 py-2.5 text-xs space-y-2">
          <div className="flex items-center justify-between gap-3">
            <span className="text-gray-500">消息范围</span>
            <span className="font-mono font-semibold text-gray-800 truncate">
              {sequenceRange ? `#${sequenceRange}` : '待确认'}
            </span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-gray-500">测试条数</span>
            <span className="font-mono font-semibold text-gray-800">
              {typeof messageCount === 'number' ? `${messageCount} 条` : '待确认'}
            </span>
          </div>
          {isFailed && (
            <div className="pt-2 border-t border-red-100 text-red-700 flex gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="font-semibold truncate">{errorType || '摘要生成失败'}</p>
                <p className="mt-0.5 break-words">{errorMessage || '任务执行失败'}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
