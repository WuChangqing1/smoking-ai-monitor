/**
 * 页面占位卡片。
 *
 * 用于尚未接入实时数据的页面：明确写出该页将展示什么、数据来自哪个接口，
 * 而不是留下一片空白或编造假内容（对应「不允许全部页面使用 mock 静态 JSON」）。
 */

import Panel from '../components/Panel'
import { Badge } from '../components/Badge'
import { IconInfo } from '../components/icons'
import './PagePlaceholder.css'

interface PagePlaceholderProps {
  /** 页面标题 */
  title: string
  /** 一句话说明该页职责 */
  summary: string
  /** 该页将展示的要点 */
  items: string[]
  /** 依赖的后端接口 */
  endpoints: string[]
  /** 交付阶段说明 */
  milestone: string
}

export default function PagePlaceholder({
  title,
  summary,
  items,
  endpoints,
  milestone,
}: PagePlaceholderProps) {
  return (
    <div className="placeholder">
      <Panel title={title} icon={<IconInfo size={14} />} extra={<Badge tone="info">{milestone}</Badge>}>
        <p className="placeholder__summary">{summary}</p>

        <div className="placeholder__cols">
          <div className="placeholder__col">
            <h4 className="placeholder__col-title">本页将展示</h4>
            <ul className="placeholder__list">
              {items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div className="placeholder__col">
            <h4 className="placeholder__col-title">依赖接口</h4>
            <ul className="placeholder__list placeholder__list--mono">
              {endpoints.map((item) => (
                <li key={item}>
                  <code>{item}</code>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="placeholder__foot">
          当前处于<strong>仿真演示环境</strong>，本页数据将由后端 SimulationEngine
          统一产生，不使用前端随机数，也不使用静态 mock 文件。
        </p>
      </Panel>
    </div>
  )
}
