/** 智能预警页 —— 轮次 7 实现未来 30 分钟风险预测与扩展能力。 */

import PagePlaceholder from '../components/PagePlaceholder'

export default function PredictionPage() {
  return (
    <PagePlaceholder
      milestone="轮次 7 实现"
      title="智能预警 · 未来 30 分钟风险预测"
      summary="这是新平台相对原项目最重要的升级点：由「异常发生后才报警」升级为「趋势预测 + 提前预警」。预测以概率形式表达，输出风险升高、建议关注、建议检查等结论，不给出确定性判断。"
      items={[
        '当前风险等级与风险指数（低 / 中 / 高 / 严重）',
        '未来 30 分钟堵料风险预测百分比与风险变化（稳定 / 上升 / 快速上升）',
        '预警依据：雷达距离连续下降时长、视觉覆盖率变化、输送速度变化、历史事件相似度',
        '相似历史事件匹配：例如与历史异常事件 A-2025-0519 的相似度',
        '扩展能力区：杂质检测（规划能力，含定位与分拣链路）、行业推广方向',
      ]}
      endpoints={['GET /api/prediction', 'GET /api/knowledge']}
    />
  )
}
