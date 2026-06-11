import { Modal } from "../ui/semi";

export function confirmAction({
  title,
  content,
  okText = "确认"
}: {
  title: string;
  content: string;
  okText?: string;
}): Promise<boolean> {
  return new Promise((resolve) => {
    Modal.confirm({
      title,
      content,
      okText,
      cancelText: "取消",
      onOk: () => resolve(true),
      onCancel: () => resolve(false)
    });
  });
}
