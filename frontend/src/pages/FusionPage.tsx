/** 雷视联动页 —— 轮次 5 实现完整融合判断与趋势图。 */

import PagePlaceholder from '../components/PagePlaceholder'

export default function FusionPage() {
  return (
    <PagePlaceholder
      milestone="轮次 5 实现"
      title="雷视联动 · 雷达与视觉互补融合"
      summary="视觉与雷达不是替代关系，而是互补：传感器负责高频快速感知，视觉负责复杂语义判断，AI 完成融合决策。本页把三者的判断过程与依据完整呈现出来。"
      items={[
        '雷达面板：当前距离、基准距离、变化量、滤波值、数据刷新状态',
        '视觉 AI 面板：检测状态、检测类别、置信度、物料覆盖率、推理耗时',
        '联合判断区：雷达 + 视觉 → 联合结论（正常 / 关注 / 预警 / 异常）与判断依据',
        '雷达距离趋势图与堆积风险趋势图，滚动保留最近 120 个数据点',
        '「为什么不能只使用视觉」能力对比：视觉的优势与限制、雷达的优势、融合的必要性',
      ]}
      endpoints={['GET /api/realtime', 'GET /api/realtime/history']}
    />
  )
}
