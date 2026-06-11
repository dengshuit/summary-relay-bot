import { Banner, Button, Collapse, Typography } from "../ui/semi";
import { IconAlertTriangle } from "@douyinfe/semi-icons";
import { useState } from "react";

const { Text } = Typography;

export function RestartBanner({ items }: { items: string[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="restart-block">
      <Banner
        type="warning"
        icon={<IconAlertTriangle />}
        description={
          <div className="banner-line">
            <span>有 {items.length} 项配置待重启生效。v1 不做在线热切换，重启服务后生效。</span>
            <Button theme="borderless" size="small" onClick={() => setOpen((value) => !value)}>
              {open ? "收起" : "查看详情"}
            </Button>
          </div>
        }
      />
      <Collapse activeKey={open ? ["detail"] : []}>
        <Collapse.Panel header="待重启配置" itemKey="detail">
          <div className="restart-list">
            {items.map((item) => (
              <Text key={item} code>
                {item}
              </Text>
            ))}
          </div>
        </Collapse.Panel>
      </Collapse>
    </div>
  );
}
