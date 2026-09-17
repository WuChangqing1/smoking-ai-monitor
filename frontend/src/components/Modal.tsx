/**
 * 通用模态窗 / 抽屉。
 *
 * 自写而不引组件库：本项目只需要一个"报警详情"弹层，
 * 依赖库在体量和样式统一性上都不划算。
 *
 * 具备基本可用性：ESC 关闭、点击遮罩关闭、打开时锁定页面滚动、
 * 关闭后恢复焦点。
 */

import { useEffect, useRef, type ReactNode } from 'react'
import './Modal.css'

interface ModalProps {
  open: boolean
  title: ReactNode
  subtitle?: ReactNode
  onClose: () => void
  /** 底部操作区 */
  footer?: ReactNode
  /** 宽度档位 */
  size?: 'md' | 'lg'
  children: ReactNode
}

export default function Modal({
  open,
  title,
  subtitle,
  onClose,
  footer,
  size = 'lg',
  children,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement | null>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)

  // ESC 关闭 + 锁定背景滚动
  useEffect(() => {
    if (!open) return

    previouslyFocused.current = document.activeElement as HTMLElement | null

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }

    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKeyDown)

    // 打开后把焦点移入弹层，便于键盘操作
    panelRef.current?.focus()

    return () => {
      window.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = prevOverflow
      previouslyFocused.current?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="modal" role="presentation" onMouseDown={onClose}>
      <div
        ref={panelRef}
        className={`modal__panel modal__panel--${size}`}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        // 阻止冒泡，避免点击内容区误关闭
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="modal__head">
          <div className="modal__titles">
            <h3 className="modal__title">{title}</h3>
            {subtitle && <p className="modal__subtitle">{subtitle}</p>}
          </div>
          <button type="button" className="modal__close" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </header>

        <div className="modal__body">{children}</div>

        {footer && <footer className="modal__foot">{footer}</footer>}
      </div>
    </div>
  )
}
