/** 知识库页 —— 轮次 7 实现基于 SQLite 的历史异常处理经验库。 */

import PagePlaceholder from '../components/PagePlaceholder'

export default function KnowledgePage() {
  return (
    <PagePlaceholder
      milestone="轮次 7 实现"
      title="知识库 · 历史异常处理经验库"
      summary="沉淀每一次异常的处理经验，形成可检索、可复用的知识条目，并作为智能预警判断相似历史模式的依据。数据库使用 SQLite，保持部署简单。"
      items={[
        '事件编号与时间：例如 EVT-20250519-02 / 2025-05-19 13:31',
        '位置与设备：制丝线 2 号输送段',
        '异常前兆模式：雷达测距由 0.71 m 逐步下降至 0.62 m，视觉覆盖率持续增加',
        '人工审核：现场确认进料量短时间升高、下游输送速度降低',
        '处理措施与结果：降低上游进料量并检查输送设备，约 4 分钟后恢复正常',
        '预防建议：可复用的操作经验，供后续预警与培训参考',
      ]}
      endpoints={['GET /api/knowledge']}
    />
  )
}
