/**
 * 视频监控页。
 *
 * 原资料存在多摄像头（点位1~点位7），但目前只有 Camera 01 具备真实画面素材。
 * 因此 Camera 01 使用真实素材，其余监控点显示低调的状态卡占位，
 * 不生成夸张的假图片（对应任务要求「多监控点」）。
 */

import Panel from '../components/Panel'
import MonitorVideo from '../components/MonitorVideo'
import { Badge, MetricList, MetricRow } from '../components/Badge'
import { IconVideo } from '../components/icons'
import type { PlatformMeta } from '../types'
import './VideoPage.css'

interface VideoPageProps {
  meta: PlatformMeta | null
  /** 主监控视频播放速率（源视频 10 s，0.5× 下演示周期约 20 s） */
  playbackRate?: number
  /** 主监控视频源时长（秒） */
  videoDuration?: number
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

/** 4 个监控点：Camera 01 有真实画面，02~04 为待切换占位 */
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
    hasStream: false,
    mode: '联合判断',
    kind: '雷达 + 视觉',
  },
  {
    camera: 'Camera 03',
    point: '制丝线 3 号工位',
    position: 3,
    deviceId: 'RAD-03',
    deviceIp: '192.168.1.199',
    hasStream: false,
    mode: '联合判断',
    kind: '雷达 + 视觉',
  },
  {
    camera: 'Camera 04',
    point: '叶线输送段',
    position: 4,
    deviceId: 'CAM-04',
    deviceIp: '192.168.1.204',
    hasStream: false,
    mode: '单独判断',
    kind: '仅视觉',
  },
]

export default function VideoPage({
  meta,
  playbackRate = 0.5,
  videoDuration = 10,
}: VideoPageProps) {
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
            <MonitorVideo cameraLabel={main.camera} timestamp={timestamp} hasStream />
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
              <MetricRow
                label="源片时长"
                value={videoDuration.toFixed(0)}
                unit="s"
                hint="主监控点演示视频的源时长"
              />
              <MetricRow
                label="播放速率"
                value={`${playbackRate}×`}
                tone="info"
                hint={`约 ${(videoDuration / playbackRate).toFixed(0)} 秒完成一个演示周期（浏览器侧调速，不重新编码）`}
              />
            </MetricList>
          </Panel>

          <Panel title="画面说明" icon={<IconVideo size={14} />}>
            <p className="video-page__note">
              原系统具备摄像头多点监控能力（点位 1~7）。当前
              <strong> Camera 01 </strong>
              已接入现场画面，其余监控点待接入完成后陆续开放，未接入前显示为待切换状态。
            </p>
            <p className="video-page__note">
              监控视频接入后，只需将文件放置为
              <code>public/videos/main-monitor.mp4</code>，全部监控点区域自动切换为视频播放，
              <strong>无需修改业务代码</strong>。
            </p>
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
                cameraLabel={slot.camera}
                showTimestamp={false}
                hasStream={slot.hasStream}
                placeholderText={`${slot.camera} 画面待切换`}
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
