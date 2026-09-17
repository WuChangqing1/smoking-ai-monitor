/** 异常报警页 —— 轮次 6 实现当前报警、历史报警与报警详情闭环。 */

import PagePlaceholder from '../components/PagePlaceholder'

export default function AlarmsPage() {
  return (
    <PagePlaceholder
      milestone="轮次 6 实现"
      title="异常报警 · 当前报警与处置闭环"
      summary="报警记录包含设备名称、设备 IP、报警时间与距离信息，与原系统报警内容口径一致；点击任意报警进入详情，形成「发现 → 判断 → 报警 → 处理 → 归档」的完整闭环。"
      items={[
        '当前报警：正在发生、尚未处理的报警，按等级排序',
        '历史报警：按时间段、设备名称、异常类型与处理状态检索',
        '报警等级：提示（绿/灰蓝）、预警（橙）、严重（红），避免满屏红色',
        '报警详情：事件基本信息 + 当时监控画面 + 雷达趋势 + AI 判断 + 处理结果',
        '处置时间线：完整还原从发现到归档的处理过程',
      ]}
      endpoints={['GET /api/alarms', 'GET /api/alarms/{id}']}
    />
  )
}
