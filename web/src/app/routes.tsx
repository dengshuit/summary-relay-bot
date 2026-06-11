import type { ReactNode } from "react";
import {
  IconServer,
  IconGridView,
  IconPulse,
  IconUserGroup,
  IconListView
} from "@douyinfe/semi-icons";

export interface NavItem {
  label: string;
  path: string;
  icon: ReactNode;
}

export const navItems: NavItem[] = [
  { label: "Dashboard", path: "/", icon: <IconGridView /> },
  { label: "Bot", path: "/bot", icon: <IconServer /> },
  { label: "摘要引擎", path: "/engine", icon: <IconPulse /> },
  { label: "群组", path: "/groups", icon: <IconUserGroup /> },
  { label: "审计日志", path: "/audit-logs", icon: <IconListView /> }
];
