import {
  IconAlertTriangle,
  IconBell,
  IconCalendar,
  IconChevronDown,
  IconChevronLeft,
  IconChevronRight,
  IconClose,
  IconInfoCircle,
  IconMore,
  IconPlus,
  IconSearch,
  IconTickCircle,
  IconUser
} from "@douyinfe/semi-icons";

const countryOptions = ["中国", "美国", "日本", "德国", "新加坡"];
const cityOptions = ["北京", "上海", "深圳", "杭州", "成都"];
const weekLabels = ["日", "一", "二", "三", "四", "五", "六"];
const mayDays = [
  "28",
  "29",
  "30",
  "1",
  "2",
  "3",
  "4",
  "5",
  "6",
  "7",
  "8",
  "9",
  "10",
  "11",
  "12",
  "13",
  "14",
  "15",
  "16",
  "17",
  "18",
  "19",
  "20",
  "21",
  "22",
  "23",
  "24",
  "25",
  "26",
  "27",
  "28",
  "29",
  "30",
  "31",
  "1"
];

function ReferenceSection({
  title,
  subtitle,
  children
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  const [cn, en] = title.split(" ");
  return (
    <section className="ref-section">
      <div className="ref-heading">
        <h1>
          {cn} <span>{en}</span>
        </h1>
        <p>{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function RefButton({
  children,
  variant = "secondary",
  size = "m",
  icon,
  disabled = false,
  loading = false
}: {
  children?: React.ReactNode;
  variant?: "primary" | "primary-soft" | "secondary" | "danger" | "danger-soft" | "text" | "icon" | "icon-primary";
  size?: "xl" | "l" | "m" | "s" | "xs";
  icon?: React.ReactNode;
  disabled?: boolean;
  loading?: boolean;
}) {
  return (
    <button
      className={`ref-button ref-button-${variant} ref-button-${size}${disabled ? " is-disabled" : ""}${
        loading ? " is-loading" : ""
      }`}
      type="button"
      disabled={disabled}
    >
      {loading && <span className="ref-spinner" />}
      {icon}
      {children}
    </button>
  );
}

function RefInput({
  label,
  value,
  placeholder = "请输入内容",
  state,
  prefix,
  suffix,
  disabled = false,
  fill = false,
  borderless = false,
  textarea = false
}: {
  label: string;
  value?: string;
  placeholder?: string;
  state?: "focus" | "success" | "error" | "warning" | "info";
  prefix?: React.ReactNode;
  suffix?: React.ReactNode;
  disabled?: boolean;
  fill?: boolean;
  borderless?: boolean;
  textarea?: boolean;
}) {
  return (
    <div className="ref-control-block">
      <div className="ref-mini-title">{label}</div>
      <div
        className={`ref-input${state ? ` is-${state}` : ""}${disabled ? " is-disabled" : ""}${
          fill ? " is-fill" : ""
        }${borderless ? " is-borderless" : ""}${textarea ? " is-textarea" : ""}`}
      >
        {prefix && <span className="ref-input-icon">{prefix}</span>}
        <span className={value ? "ref-input-value" : "ref-input-placeholder"}>{value || placeholder}</span>
        {textarea && <span className="ref-count">0 / 200</span>}
        {suffix && <span className="ref-input-icon right">{suffix}</span>}
      </div>
      {state === "error" && <div className="ref-error-text">请输入正确的内容</div>}
    </div>
  );
}

function RefSelect({
  label,
  value,
  placeholder = "请选择",
  state,
  tags,
  disabled = false
}: {
  label: string;
  value?: string;
  placeholder?: string;
  state?: "focus" | "success" | "error" | "warning" | "info";
  tags?: string[];
  disabled?: boolean;
}) {
  return (
    <div className="ref-control-block">
      <div className="ref-mini-title">{label}</div>
      <div className={`ref-select${state ? ` is-${state}` : ""}${disabled ? " is-disabled" : ""}`}>
        {tags ? (
          <span className="ref-select-tags">
            {tags.map((tag) => (
              <span className="ref-select-tag" key={tag}>
                {tag}
                <IconClose />
              </span>
            ))}
          </span>
        ) : (
          <span className={value ? "ref-input-value" : "ref-input-placeholder"}>{value || placeholder}</span>
        )}
        <IconChevronDown />
      </div>
    </div>
  );
}

function DropdownPanel({
  type = "basic",
  selected = "中国"
}: {
  type?: "basic" | "icons" | "grouped" | "search" | "multi";
  selected?: string;
}) {
  if (type === "multi") {
    const options = ["React", "Vue", "Angular", "Svelte", "SolidJS"];
    return (
      <div className="ref-dropdown is-multi">
        {options.map((option, index) => (
          <div className="ref-check-option" key={option}>
            <span className={`ref-checkbox${index === 2 || index === 4 ? "" : " is-checked"}`} />
            {option}
          </div>
        ))}
        <div className="ref-dropdown-footer">
          <span>已选择 3 项</span>
          <button type="button">确定</button>
        </div>
      </div>
    );
  }
  if (type === "search") {
    return (
      <div className="ref-dropdown">
        <div className="ref-dropdown-search">
          <IconSearch />
        </div>
        {cityOptions.map((option) => (
          <div className={`ref-option${option === "北京" ? " is-active" : ""}`} key={option}>
            {option}
          </div>
        ))}
      </div>
    );
  }
  if (type === "grouped") {
    return (
      <div className="ref-dropdown">
        <div className="ref-option-group">华北地区</div>
        {["北京", "天津", "石家庄"].map((option) => (
          <div className="ref-option" key={option}>
            {option}
          </div>
        ))}
        <div className="ref-option-group">华东地区</div>
        {["上海", "杭州"].map((option) => (
          <div className="ref-option" key={option}>
            {option}
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="ref-dropdown">
      {countryOptions.map((option, index) => (
        <div className={`ref-option${option === selected ? " is-selected" : ""}`} key={option}>
          {type === "icons" && <span className={`ref-flag flag-${index}`} />}
          {option}
          {option === selected && <span className="ref-check">✓</span>}
        </div>
      ))}
    </div>
  );
}

function CalendarPanel({ range = false, time = false }: { range?: boolean; time?: boolean }) {
  return (
    <div className={`ref-calendar${range ? " is-range" : ""}${time ? " has-time" : ""}`}>
      <div className="ref-calendar-main">
        <div className="ref-calendar-head">
          <IconChevronLeft />
          <strong>2024 年 5 月</strong>
          <IconChevronRight />
        </div>
        <div className="ref-week-grid">
          {weekLabels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
        <div className="ref-day-grid">
          {mayDays.map((day, index) => {
            const muted = index < 3 || index > 33;
            const selected = day === "15" || (range && day === "23");
            const inRange = range && index >= 17 && index <= 26;
            return (
              <span
                className={`${muted ? "is-muted" : ""}${selected ? " is-selected" : ""}${
                  inRange ? " is-in-range" : ""
                }`}
                key={`${day}-${index}`}
              >
                {day}
              </span>
            );
          })}
        </div>
        <div className="ref-calendar-footer">
          <span>今天</span>
          <span>清空</span>
          {range && <button type="button">确定</button>}
        </div>
      </div>
      {time && (
        <div className="ref-time-list">
          {["12:00", "13:00", "14:30", "15:00", "16:00"].map((item) => (
            <span className={item === "14:30" ? "is-selected" : ""} key={item}>
              {item}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function RefTag({
  children,
  tone = "neutral",
  removable = false,
  icon
}: {
  children: React.ReactNode;
  tone?: "neutral" | "primary" | "success" | "warning" | "danger" | "info";
  removable?: boolean;
  icon?: React.ReactNode;
}) {
  return (
    <span className={`ref-tag ref-tag-${tone}`}>
      {icon}
      {children}
      {removable && <IconClose />}
    </span>
  );
}

function Message({ tone, children }: { tone: "success" | "danger" | "warning" | "info"; children: React.ReactNode }) {
  const icon =
    tone === "success" ? <IconTickCircle /> : tone === "info" ? <IconInfoCircle /> : <IconAlertTriangle />;
  return (
    <div className={`ref-message ref-message-${tone}`}>
      {icon}
      <span>{children}</span>
      <IconClose />
    </div>
  );
}

function RefField({
  label,
  required = false,
  children,
  error
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
  error?: string;
}) {
  return (
    <label className="ref-field">
      <span>
        {label}
        {required && <b>*</b>}
      </span>
      {children}
      {error && <em>{error}</em>}
    </label>
  );
}

function ProjectTable({ compact = false, loading = false }: { compact?: boolean; loading?: boolean }) {
  const rows = [
    ["1001", "AI 数据分析平台", "张三", "进行中", "60%"],
    ["1002", "智能客服系统", "李四", "已完成", "100%"],
    ["1003", "推荐算法优化", "王五", "已暂停", "30%"],
    ["1004", "用户增长活动", "赵六", "未开始", "0%"],
    ["1005", "数据中台建设", "孙七", "进行中", "70%"]
  ];
  return (
    <div className={`ref-table-card${compact ? " is-compact" : ""}`}>
      <table className="ref-table">
        <thead>
          <tr>
            {!compact && <th />}
            <th>ID</th>
            <th>项目名称</th>
            {!compact && <th>负责人</th>}
            <th>状态</th>
            {!compact && <th>进度</th>}
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? rows.slice(0, 4).map((row) => (
                <tr className="is-loading" key={row[0]}>
                  {!compact && <td />}
                  <td>
                    <span />
                  </td>
                  <td>
                    <span />
                  </td>
                  {!compact && (
                    <td>
                      <span />
                    </td>
                  )}
                  <td>
                    <span />
                  </td>
                  {!compact && (
                    <td>
                      <span />
                    </td>
                  )}
                  <td>
                    <span />
                  </td>
                  <td>...</td>
                </tr>
              ))
            : rows.slice(0, compact ? 2 : 5).map((row, index) => (
                <tr className={index === 2 ? "is-selected" : ""} key={row[0]}>
                  {!compact && (
                    <td>
                      <span className={`ref-checkbox${index === 2 ? " is-checked" : ""}`} />
                    </td>
                  )}
                  <td>{row[0]}</td>
                  <td>
                    <strong>{row[1]}</strong>
                  </td>
                  {!compact && <td>{row[2]}</td>}
                  <td>
                    <span className={`ref-status-dot ${index === 1 ? "success" : index === 2 ? "warning" : "primary"}`}>
                      {row[3]}
                    </span>
                  </td>
                  {!compact && (
                    <td>
                      <span className="ref-progress">
                        <i style={{ width: row[4] }} />
                      </span>
                      {row[4]}
                    </td>
                  )}
                  <td>2024-06-01</td>
                  <td>
                    <a>查看</a>
                    <a>编辑</a>
                    <IconMore />
                  </td>
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  );
}

export function ComponentReference() {
  return (
    <div className="component-reference-page">
      <ReferenceSection title="按钮 Button" subtitle="Semi Design 风格按钮示例：使用轻量、简洁、现代的视觉语言，支持多种类型、状态和尺寸。">
        <div className="ref-row is-button-types">
          <div className="ref-row-title">类型</div>
          <div>
            <h3>主要按钮（积极）</h3>
            <RefButton variant="primary">主要按钮</RefButton>
            <RefButton variant="primary-soft">主要按钮</RefButton>
          </div>
          <div>
            <h3>次要按钮（中性）</h3>
            <RefButton>次要按钮</RefButton>
            <RefButton>次要按钮</RefButton>
          </div>
          <div>
            <h3>危险按钮（消极）</h3>
            <RefButton variant="danger">删除</RefButton>
            <RefButton variant="danger-soft">删除</RefButton>
          </div>
          <div>
            <h3>文本按钮</h3>
            <RefButton variant="text">文本按钮</RefButton>
            <RefButton variant="text">文本按钮</RefButton>
          </div>
          <div>
            <h3>图标按钮</h3>
            <div className="ref-inline">
              <RefButton variant="icon" icon={<IconPlus />} />
              <RefButton variant="icon-primary" icon={<IconPlus />} />
            </div>
            <div className="ref-inline">
              <RefButton variant="icon" icon={<IconPlus />} />
              <RefButton variant="icon-primary" icon={<IconPlus />} />
            </div>
          </div>
        </div>
        <div className="ref-row is-size-row">
          <div className="ref-row-title">尺寸</div>
          {[
            ["超大（XL）", "xl"],
            ["大（L）", "l"],
            ["中（M）", "m"],
            ["小（S）", "s"],
            ["超小（XS）", "xs"]
          ].map(([label, size]) => (
            <div key={label}>
              <h3>{label}</h3>
              <RefButton variant="primary" size={size as "xl" | "l" | "m" | "s" | "xs"}>
                主要按钮
              </RefButton>
            </div>
          ))}
        </div>
        <div className="ref-row is-state-row">
          <div className="ref-row-title">状态</div>
          <div>
            <h3>默认（Default）</h3>
            <RefButton variant="primary">主要按钮</RefButton>
          </div>
          <div>
            <h3>悬停（Hover）</h3>
            <RefButton variant="primary" size="m">
              主要按钮
            </RefButton>
          </div>
          <div>
            <h3>点击（Active）</h3>
            <RefButton variant="primary" size="m">
              主要按钮
            </RefButton>
          </div>
          <div>
            <h3>禁用（Disabled）</h3>
            <RefButton variant="primary" disabled>
              主要按钮
            </RefButton>
          </div>
          <div>
            <h3>加载中（Loading）</h3>
            <RefButton variant="primary" loading>
              加载中
            </RefButton>
          </div>
        </div>
      </ReferenceSection>

      <ReferenceSection title="输入框 Input" subtitle="Semi Design 风格输入框示例：简洁、清晰、状态明确，支持多种类型和状态。">
        <div className="ref-grid ref-grid-6">
          <RefInput label="默认" />
          <RefInput label="悬停" />
          <RefInput label="聚焦" state="focus" />
          <RefInput label="已输入" value="Semi Design" />
          <RefInput label="禁用" disabled />
          <RefInput label="只读" value="只读内容" disabled={false} fill />
        </div>
        <div className="ref-divider" />
        <div className="ref-grid ref-grid-6">
          <RefInput label="左侧图标" prefix={<IconSearch />} placeholder="搜索内容" />
          <RefInput label="右侧图标" suffix={<IconCalendar />} />
          <RefInput label="左右图标" prefix={<IconSearch />} suffix={<IconClose />} placeholder="搜索内容" />
          <RefInput label="可清除" value="Semi Design" suffix={<IconClose />} />
          <RefInput label="密码输入" prefix={<IconUser />} value="••••••••" suffix={<IconInfoCircle />} />
          <RefInput label="组合图标" prefix={<IconUser />} placeholder="用户名" suffix={<IconChevronDown />} />
        </div>
        <div className="ref-divider" />
        <div className="ref-grid ref-grid-5">
          <RefInput label="超大（XL）" />
          <RefInput label="大（L）" />
          <RefInput label="中（M）" />
          <RefInput label="小（S）" />
          <RefInput label="超小（XS）" />
        </div>
        <div className="ref-divider" />
        <div className="ref-grid ref-grid-4">
          <RefInput label="成功（Success）" state="success" value="输入正确" suffix={<IconTickCircle />} />
          <RefInput label="错误（Error）" state="error" value="输入有误" suffix={<IconAlertTriangle />} />
          <RefInput label="警告（Warning）" state="warning" suffix={<IconAlertTriangle />} />
          <RefInput label="信息（Info）" state="info" suffix={<IconInfoCircle />} />
        </div>
        <div className="ref-divider" />
        <div className="ref-grid ref-grid-5">
          <RefInput label="描边款（默认）" />
          <RefInput label="填充款" fill />
          <RefInput label="无边框" borderless />
          <RefInput label="文本域（Textarea）" textarea />
          <div className="ref-control-block">
            <div className="ref-mini-title">搜索框</div>
            <div className="ref-search-combo">
              <IconSearch />
              <span>搜索内容</span>
              <button type="button">搜索</button>
            </div>
          </div>
        </div>
      </ReferenceSection>

      <ReferenceSection title="选择器 Select" subtitle="Semi Design 风格选择器示例：简洁、清晰、状态明确，支持多种类型和状态。">
        <div className="ref-grid ref-grid-6">
          <RefSelect label="默认" />
          <RefSelect label="已选中" value="中国" />
          <RefSelect label="悬停" state="focus" />
          <RefSelect label="聚焦" state="focus" />
          <RefSelect label="禁用" disabled />
          <RefSelect label="多选（Tags）" tags={["中国", "美国"]} />
        </div>
        <div className="ref-divider" />
        <div className="ref-dropdown-showcase">
          <div>
            <RefSelect label="基础下拉" state="focus" />
            <DropdownPanel />
          </div>
          <div>
            <RefSelect label="带图标" placeholder="选择国家/地区" />
            <DropdownPanel type="icons" />
          </div>
          <div>
            <RefSelect label="带分组" placeholder="选择城市" />
            <DropdownPanel type="grouped" />
          </div>
          <div>
            <RefSelect label="可搜索" placeholder="搜索城市" />
            <DropdownPanel type="search" />
          </div>
          <div>
            <RefSelect label="多选（下拉面板）" placeholder="选择技术栈" />
            <DropdownPanel type="multi" />
          </div>
          <div>
            <RefSelect label="可清除" value="中国" />
          </div>
        </div>
        <div className="ref-divider" />
        <div className="ref-grid ref-grid-4">
          <RefSelect label="成功" state="success" value="已通过" />
          <RefSelect label="错误" state="error" value="验证失败" />
          <RefSelect label="警告" state="warning" value="存在风险" />
          <RefSelect label="信息" state="info" value="处理中" />
        </div>
      </ReferenceSection>

      <ReferenceSection title="日期选择器 DatePicker" subtitle="Semi Design 风格日期选择器示例：简洁、清晰、易用，支持多种选择模式和状态。">
        <div className="ref-datepicker-row">
          <div>
            <RefInput label="单个日期" placeholder="选择日期" suffix={<IconCalendar />} />
            <CalendarPanel />
          </div>
          <div>
            <RefInput label="日期范围" placeholder="开始日期     →     结束日期" suffix={<IconCalendar />} />
            <CalendarPanel range />
          </div>
          <div>
            <RefInput label="日期时间" placeholder="选择日期时间" suffix={<IconCalendar />} />
            <CalendarPanel time />
          </div>
        </div>
        <div className="ref-divider" />
        <div className="ref-grid ref-grid-7">
          <RefInput label="默认状态" placeholder="选择日期" suffix={<IconCalendar />} />
          <RefInput label="悬停状态" placeholder="选择日期" suffix={<IconCalendar />} />
          <RefInput label="聚焦状态" state="focus" placeholder="选择日期" suffix={<IconCalendar />} />
          <RefInput label="已选择" value="2024-05-15" suffix={<IconCalendar />} />
          <RefInput label="禁用状态" disabled placeholder="选择日期" suffix={<IconCalendar />} />
          <RefInput label="错误状态" state="error" placeholder="选择日期" suffix={<IconCalendar />} />
          <RefInput label="清空状态" placeholder="请选择日期" suffix={<IconClose />} />
        </div>
      </ReferenceSection>

      <ReferenceSection title="数据标签 Tag" subtitle="Semi Design 风格数据标签用于展示状态、分类、数量等信息，轻量、清晰、易读。">
        <div className="ref-grid ref-grid-6">
          <div>
            <h3>默认</h3>
            <RefTag>标签</RefTag>
          </div>
          <div>
            <h3>主要（主色）</h3>
            <RefTag tone="primary">标签</RefTag>
          </div>
          <div>
            <h3>成功</h3>
            <RefTag tone="success">标签</RefTag>
          </div>
          <div>
            <h3>警告</h3>
            <RefTag tone="warning">标签</RefTag>
          </div>
          <div>
            <h3>危险</h3>
            <RefTag tone="danger">标签</RefTag>
          </div>
          <div>
            <h3>信息</h3>
            <RefTag tone="info">标签</RefTag>
          </div>
        </div>
        <div className="ref-divider" />
        <div className="ref-inline ref-tag-band">
          <RefTag tone="primary" icon={<IconInfoCircle />}>
            AI 模型
          </RefTag>
          <RefTag tone="success" icon={<IconTickCircle />}>
            运行中
          </RefTag>
          <RefTag tone="warning" icon={<IconAlertTriangle />}>
            待处理
          </RefTag>
          <RefTag tone="danger" icon={<IconClose />}>
            失败
          </RefTag>
          <RefTag tone="info" icon={<IconBell />}>
            通知
          </RefTag>
          <RefTag tone="primary" removable>
            React
          </RefTag>
          <RefTag tone="info" removable>
            TypeScript
          </RefTag>
          <RefTag removable>设计系统</RefTag>
        </div>
        <div className="ref-divider" />
        <div className="ref-message-grid">
          <Message tone="success">操作成功</Message>
          <Message tone="danger">操作失败，请重试</Message>
          <Message tone="warning">资源已过期，请重新获取</Message>
          <Message tone="info">数据加载中，请稍候</Message>
        </div>
      </ReferenceSection>

      <ReferenceSection title="表单 Form" subtitle="Semi Design 风格表单示例：简洁、清晰、易用，支持多种表单控件和状态。">
        <div className="ref-form-grid">
          <div className="ref-form-card">
            <h2>基础表单</h2>
            <RefField label="项目名称" required>
              <RefInput label="" placeholder="请输入项目名称" />
            </RefField>
            <RefField label="项目类型" required>
              <RefSelect label="" placeholder="请选择项目类型" />
            </RefField>
            <RefField label="负责人" required>
              <RefSelect label="" tags={["张三"]} />
            </RefField>
            <RefField label="描述">
              <RefInput label="" textarea placeholder="请输入项目描述" />
            </RefField>
            <RefField label="开始时间">
              <RefInput label="" placeholder="选择开始日期" suffix={<IconCalendar />} />
            </RefField>
            <div className="ref-switch-line">
              <span>公开项目</span>
              <i />
            </div>
            <div className="ref-form-actions">
              <RefButton>取消</RefButton>
              <RefButton variant="primary">提交</RefButton>
            </div>
          </div>
          <div className="ref-form-card">
            <h2>水平布局表单</h2>
            <RefField label="项目名称" required>
              <RefInput label="" />
            </RefField>
            <RefField label="项目类型" required>
              <RefSelect label="" />
            </RefField>
            <RefField label="开始时间">
              <RefInput label="" placeholder="选择日期" suffix={<IconCalendar />} />
            </RefField>
            <RefField label="结束时间">
              <RefInput label="" placeholder="选择日期" suffix={<IconCalendar />} />
            </RefField>
            <RefField label="优先级">
              <div className="ref-radio-row">
                <span className="is-checked" />高 <span />中 <span />低
              </div>
            </RefField>
            <RefField label="描述">
              <RefInput label="" textarea />
            </RefField>
            <div className="ref-form-actions">
              <RefButton>取消</RefButton>
              <RefButton variant="primary">提交</RefButton>
            </div>
          </div>
          <div className="ref-form-card">
            <h2>分组表单</h2>
            <div className="ref-form-group-title">基本信息</div>
            <RefField label="项目名称" required>
              <RefInput label="" />
            </RefField>
            <RefField label="项目类型" required>
              <RefSelect label="" />
            </RefField>
            <div className="ref-form-group-title">时间信息</div>
            <RefField label="开始时间">
              <RefInput label="" placeholder="选择开始日期" suffix={<IconCalendar />} />
            </RefField>
            <RefField label="结束时间">
              <RefInput label="" placeholder="选择结束日期" suffix={<IconCalendar />} />
            </RefField>
            <div className="ref-form-actions">
              <RefButton>取消</RefButton>
              <RefButton variant="primary">提交</RefButton>
            </div>
          </div>
          <div className="ref-form-card">
            <h2>表单状态</h2>
            <h3>填写中</h3>
            <RefField label="项目名称" required>
              <RefInput label="" value="AI 数据分析平台" />
            </RefField>
            <RefField label="项目类型" required>
              <RefSelect label="" value="AI应用" />
            </RefField>
            <h3>验证错误</h3>
            <RefField label="项目名称" required error="项目名称不能为空">
              <RefInput label="" state="error" placeholder="请输入项目名称" />
            </RefField>
            <RefField label="项目类型" required error="请选择项目类型">
              <RefSelect label="" state="error" placeholder="请选择项目类型" />
            </RefField>
            <h3>禁用状态</h3>
            <RefField label="项目名称">
              <RefInput label="" value="AI 数据分析平台" disabled />
            </RefField>
          </div>
        </div>
      </ReferenceSection>

      <ReferenceSection title="表格 Table" subtitle="Semi Design 风格表格示例：简洁、清晰、易用，支持多种状态和交互。">
        <div className="ref-table-layout">
          <div>
            <div className="ref-table-toolbar">
              <h2>基础表格</h2>
              <div>
                <div className="ref-toolbar-input">
                  <IconSearch />
                  <span>搜索项目名称</span>
                </div>
                <RefButton>筛选</RefButton>
                <RefButton variant="primary" icon={<IconPlus />}>
                  新建项目
                </RefButton>
              </div>
            </div>
            <ProjectTable />
            <div className="ref-pagination">
              <span>共 32 条</span>
              <button type="button">
                <IconChevronLeft />
              </button>
              <button className="is-active" type="button">
                1
              </button>
              <button type="button">2</button>
              <button type="button">3</button>
              <button type="button">4</button>
              <button type="button">5</button>
              <span>...</span>
              <button type="button">8</button>
              <button type="button">
                <IconChevronRight />
              </button>
              <button className="ref-page-size" type="button">
                10 条/页 <IconChevronDown />
              </button>
            </div>
          </div>
          <aside className="ref-note-card">
            <h2>表格说明</h2>
            {["表头固定：滚动时表头保持可见", "斑马纹：提升行可读性", "悬停态：鼠标悬停高亮整行", "复选框：支持批量选择", "状态标签：使用轻量标签展示状态", "操作列：支持更多操作"].map(
              (item, index) => (
                <p key={item}>
                  <b>{index + 1}</b>
                  {item}
                </p>
              )
            )}
          </aside>
        </div>
        <div className="ref-grid ref-grid-3 ref-table-states">
          <div>
            <h2>紧凑表格</h2>
            <ProjectTable compact />
          </div>
          <div className="ref-empty-box">
            <h2>无数据</h2>
            <div className="ref-empty-icon" />
            <p>暂无数据</p>
            <RefButton variant="primary" icon={<IconPlus />}>
              新建项目
            </RefButton>
          </div>
          <div>
            <h2>加载中</h2>
            <ProjectTable loading />
          </div>
        </div>
      </ReferenceSection>
    </div>
  );
}
