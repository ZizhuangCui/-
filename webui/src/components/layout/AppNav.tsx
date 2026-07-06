import { ActivitySquare, BellRing, FolderOpen, MessageSquareText } from 'lucide-react'
import { cn } from '@/lib/utils'

export type AppPage = 'crawler' | 'comments' | 'files' | 'broadcast'

type NavItem = {
  id: AppPage
  label: string
  description: string
  icon: typeof ActivitySquare
}

const navItems: NavItem[] = [
  {
    id: 'crawler',
    label: '采集控制台',
    description: '原始爬虫任务',
    icon: ActivitySquare,
  },
  {
    id: 'comments',
    label: '评论区管理',
    description: '抖音 / 小红书 / Bilibili',
    icon: MessageSquareText,
  },
  {
    id: 'files',
    label: '文件中心',
    description: 'CSV / 汇总表 / 风险表',
    icon: FolderOpen,
  },
  {
    id: 'broadcast',
    label: '播报配置',
    description: '飞书群机器人 / 预览',
    icon: BellRing,
  },
]

type AppNavProps = {
  currentPage: AppPage
  onPageChange: (page: AppPage) => void
}

export function AppNav({ currentPage, onPageChange }: AppNavProps) {
  return (
    <aside className="w-[236px] flex-shrink-0 border-r border-cyber-border-subtle glass-panel relative z-10 overflow-hidden">
      <nav className="h-full p-3 flex flex-col gap-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = currentPage === item.id

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onPageChange(item.id)}
              className={cn(
                'w-full h-[68px] rounded-md border px-3 text-left transition-all flex items-center gap-3',
                isActive
                  ? 'border-cyber-neon-cyan/60 bg-cyber-neon-cyan/10 shadow-glow-cyan-sm'
                  : 'border-cyber-border-subtle bg-cyber-bg-tertiary/30 hover:border-cyber-neon-cyan/40 hover:bg-cyber-bg-tertiary/60'
              )}
            >
              <span
                className={cn(
                  'h-9 w-9 rounded-md border flex items-center justify-center flex-shrink-0',
                  isActive
                    ? 'border-cyber-neon-cyan/50 bg-cyber-neon-cyan/15'
                    : 'border-cyber-border-subtle bg-cyber-bg-panel/50'
                )}
              >
                <Icon className={cn('h-4 w-4', isActive ? 'text-cyber-neon-cyan' : 'text-cyber-text-secondary')} />
              </span>
              <span className="min-w-0">
                <span className={cn('block text-sm font-mono font-semibold', isActive ? 'text-cyber-neon-cyan' : 'text-cyber-text-primary')}>
                  {item.label}
                </span>
                <span className="block text-[11px] text-cyber-text-muted truncate">
                  {item.description}
                </span>
              </span>
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
