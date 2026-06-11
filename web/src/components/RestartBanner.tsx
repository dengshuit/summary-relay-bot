import { IconAlertTriangle, IconChevronDown } from "@douyinfe/semi-icons";
import { useState } from "react";

export function RestartBanner({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="restart-block">
      <div className="restart-banner">
        <div className="restart-banner-icon">
          <IconAlertTriangle />
        </div>
        <div className="restart-banner-text">
          有 <b>{items.length} 项</b>配置变更待重启生效。重启服务后生效，期间运行仍使用旧配置。
        </div>
        <button
          className="restart-banner-action"
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "收起" : "查看详情"}
          <IconChevronDown className={open ? "is-open" : ""} />
        </button>
      </div>
      {open && (
        <div className="restart-detail">
          <div className="restart-detail-title">待重启生效的变更</div>
          <div className="restart-list">
            {items.map((item) => (
              <span className="restart-pill" key={item}>
                {item}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
