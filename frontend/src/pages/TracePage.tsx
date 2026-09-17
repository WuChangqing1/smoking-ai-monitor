/** 数据溯源页 —— 轮次 6 实现多维筛选与历史事件检索。 */

import PagePlaceholder from '../components/PagePlaceholder'

export default function TracePage() {
  return (
    <PagePlaceholder
      milestone="轮次 6 实现"
      title="数据溯源 · 历史事件检索"
      summary="支持按时间范围、设备、异常类型、风险等级与处理状态组合检索历史事件，并可回溯查看当时的雷达数据、视觉结果与处置记录。"
      items={[
        '日期范围筛选：按报警时间段查询（与原系统「按时间段查询」一致）',
        '设备筛选：按设备名称 / 设备编号查询',
        '异常类型筛选：物料堆积、输送速度下降、人员进入检测区等',
        '风险等级筛选：低 / 中 / 高 / 严重',
        '状态筛选：待处理 / 处理中 / 已处理 / 已归档',
        '结果明细：可下钻到具体事件的关联数据与图像',
      ]}
      endpoints={['GET /api/alarms', 'GET /api/devices', 'GET /api/alarms/{id}']}
    />
  )
}
