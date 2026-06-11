import { useEffect, useRef, useState } from "react";
import { Button, Toast, Typography } from "../ui/semi";
import { IconPlay, IconTickCircle, IconAlertCircle } from "@douyinfe/semi-icons";
import { ApiError, api } from "../api/client";
import type { SummaryJob } from "../api/types";
import { StatusBadge } from "./StatusBadge";

const { Text } = Typography;
const terminalStatuses = new Set(["succeeded", "failed", "blocked"]);

export function JobStatusButton({
  groupId,
  disabled,
  onFinished
}: {
  groupId: number;
  disabled?: boolean;
  onFinished?: () => void;
}) {
  const [job, setJob] = useState<SummaryJob | null>(null);
  const [pollUrl, setPollUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!pollUrl || (job && terminalStatuses.has(job.status))) {
      return;
    }
    timerRef.current = window.setTimeout(async () => {
      try {
        const nextJob = await api.groups.pollJob(pollUrl);
        setJob(nextJob);
        if (terminalStatuses.has(nextJob.status)) {
          onFinished?.();
        }
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 401)) {
          Toast.error("轮询摘要任务失败");
        }
      }
    }, 1500);
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, [job, onFinished, pollUrl]);

  async function trigger() {
    setLoading(true);
    try {
      const response = await api.groups.triggerSummary(groupId);
      setJob(response.job);
      setPollUrl(response.poll_url);
      Toast.success("摘要任务已提交");
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        Toast.warning("该群有摘要正在生成");
      }
    } finally {
      setLoading(false);
    }
  }

  const running = loading || (job !== null && !terminalStatuses.has(job.status));
  return (
    <div className="job-trigger">
      <Button
        theme="solid"
        type="primary"
        icon={job?.status === "succeeded" ? <IconTickCircle /> : <IconPlay />}
        loading={running}
        disabled={disabled || running}
        onClick={trigger}
      >
        {running ? "生成中" : job?.status === "succeeded" ? "已生成" : "手动触发摘要"}
      </Button>
      {job && (
        <div className="job-state">
          <StatusBadge status={job.status} />
          {(job.error_type || job.error_message) && (
            <Text type="danger" size="small">
              <IconAlertCircle /> {job.error_type || "summary_failed"} {job.error_message || ""}
            </Text>
          )}
        </div>
      )}
    </div>
  );
}
