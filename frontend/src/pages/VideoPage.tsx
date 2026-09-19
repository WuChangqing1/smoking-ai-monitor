/**
 * 视频监控页。
 *
 * Camera 01 为主监控画面：参与全站数据同步，并叠加异常检测框。
 * Camera 02~04 使用同一份现场素材循环播放（0.5×），不参与数据同步。
 */

import Panel from '../components/Panel'
import MonitorVideo, { cameraVideoSrc } from '../components/MonitorVideo'
import { Badge, MetricList, MetricRow } from '../components/Badge'
import { IconVideo } from '../components/icons'
import type { PlatformMeta } from '../types'
import './VideoPage.css'

interface VideoPageProps {
  meta: PlatformMeta | null
}

interface PointSlot {
  camera: string
  point: string
  position: number
  deviceId: string
  deviceIp: string
  hasStream: boolean
  mode: string
  kind: '雷达 + 视觉' | '仅视觉'
}

/**
 * 4 个监控点。Camera 01 为主监控画面（参与全站数据同步 + 异常检测框）；
 * Camera 02~04 使用同一份现场素材循环播放。
 *
 * 注意：机位编号与点位号是两套编号 —— 主监控画面是 Camera 01，
 * 对应点位 2（制丝线 2 号输送段）；Camera 02 对应点位 1。
 * 该映射与后端 devices.py 的 CAMERA_NUMBER 保持一致。
 */
const POINTS: PointSlot[] = [
  {
    camera: 'Camera 01',
    point: '制丝线 2 号工位',
    position: 2,
    deviceId: 'RAD-02',
    deviceIp: '192.168.1.198',
    hasStream: true,
    mode: '主监控点',
    kind: '雷达 + 视觉',
  },
  {
    camera: 'Camera 02',
    point: '制丝线 1 号工位',
    position: 1,
    deviceId: 'RAD-01',
    deviceIp: '192.168.1.197',
    hasStream: true,
    mode: '联合判断',
    kind: '雷达 + 视觉',
  },
  {
    camera: 'Camera 03',
    point: '制丝线 3 号工位',
    position: 3,
    deviceId: 'RAD-03',
    deviceIp: '192.168.1.199',
    hasStream: true,
    mode: '联合判断',
    kind: '雷达 + 视觉',
  },
  {
    camera: 'Camera 04',
    point: '叶线输送段',
    position: 4,
    deviceId: 'CAM-04',
    deviceIp: '192.168.1.204',
    hasStream: true,
    mode: '单独判断',
    kind: '仅视觉',
  },
]

export default function VideoPage({ meta }: VideoPageProps) {
  const main = POINTS[0]
  const timestamp = new Date().toLocaleString('zh-CN', { hour12: false })

  return (
    <div className="video-page">
      <div className="video-page__layout">
        <Panel
          tone="primary"
          flush
          title={`主监控画面 · ${main.camera}`}
          icon={<IconVideo size={14} />}
          description={`${main.point} · 设备 ${main.deviceId} · ${main.deviceIp}`}
          extra={
            <>
              <Badge tone="normal" dot>
                在线
              </Badge>
              <Badge tone="primary" dot>
                AI 检测中
              </Badge>
            </>
          }
        >
          <div className="video-page__main-wrap">
            <MonitorVideo timestamp={timestamp} hasStream />
          </div>
        </Panel>

        <div className="video-page__side">
          <Panel title="监控点概览" icon={<IconVideo size={14} />}>
            <MetricList>
              <MetricRow label="监控点总数" value={meta?.monitor_points ?? 7} unit="个" />
              <MetricRow label="已接入画面" value={1} unit="路" tone="normal" />
              <MetricRow label="摄像机" value={meta?.devices.camera ?? 15} unit="台" />
              <MetricRow label="激光雷达" value={meta?.devices.radar ?? 3} unit="台" />
              <MetricRow
                label="视频编码"
                value="H.265"
                tone="info"
                hint="海康威视 DS-2CD2242CX8-L，400 万像素，25 fps"
              />
            </MetricList>
          </Panel>
        </div>
      </div>

      {/* ---- 多监控点缩略区 ---- */}
      <div className="grid grid--4 video-page__grid">
        {POINTS.slice(1).map((slot) => (
          <Panel
            key={slot.camera}
            flush
            title={slot.camera}
            icon={<IconVideo size={14} />}
            extra={<Badge tone="idle">{slot.mode}</Badge>}
          >
            <div className="video-page__thumb">
              <MonitorVideo
                showTimestamp={false}
                hasStream={slot.hasStream}
                placeholderText={`${slot.camera} 画面待切换`}
                /* 各机位播放各自的现场素材，同样 0.5× 循环播放 */
                videoSrc={cameraVideoSrc(slot.camera)}
              />
            </div>
            <div className="video-page__thumb-meta">
              <span>{slot.point}</span>
              <span className="mono">{slot.deviceId}</span>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  )
}
