import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BellRing, Bot, CheckCircle2, Clock3, Eye, Loader2, MessageSquareWarning, Play, QrCode, Settings2, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useStartCrawler } from '@/hooks/useCrawler'
import { crawlerApi, monitorApi, type LoginStatus, type MonitorJobStatus } from '@/lib/api'
import { useCrawlerStore } from '@/store/crawlerStore'
import type { CrawlerConfig } from '@/types/crawler'

type PlatformKey = 'dy' | 'xhs' | 'bili'
type CrawlerMode = 'search' | 'detail' | 'creator'
type LoginType = 'qrcode' | 'cookie'

type PlatformConfig = {
  enabled: boolean
  crawlerType: CrawlerMode
  targetValue: string
  riskWords: string
  loginType: LoginType
  cookies: string
  headless: boolean
  interval: string
  maxNotesMode: 'limit' | 'all'
  maxNotes: number
  maxCommentsMode: 'limit' | 'all'
  maxComments: number
  includeSubComments: boolean
  notify: boolean
}

type PlatformMeta = {
  id: PlatformKey
  name: string
  logo: string
  description: string
}

const platforms: PlatformMeta[] = [
  {
    id: 'dy',
    name: '抖音',
    logo: '/logos/douyin.png',
    description: '监控指定账号全部视频与评论区风险内容',
  },
  {
    id: 'xhs',
    name: '小红书',
    logo: '/logos/xiaohongshu_logo.png',
    description: '监控指定账号全部笔记与版权相关反馈',
  },
  {
    id: 'bili',
    name: 'Bilibili',
    logo: '/logos/bilibili_logo.png',
    description: '监控指定账号全部视频评论区与投诉线索',
  },
]

const defaultRiskWords = '版权,侵权,盗版,抄袭,搬运,未经授权,投诉,举报,律师函,起诉,下架'
const allItemsLimit = 10000
const knownXhsAccountMap: Record<string, string> = {
  '63566726289': '69710df20000000037003af2',
}

const initialConfig: Record<PlatformKey, PlatformConfig> = {
  dy: {
    enabled: false,
    crawlerType: 'creator',
    targetValue: '',
    riskWords: defaultRiskWords,
    loginType: 'qrcode',
    cookies: '',
    headless: false,
    interval: 'hourly',
    maxNotesMode: 'limit',
    maxNotes: 20,
    maxCommentsMode: 'limit',
    maxComments: 50,
    includeSubComments: false,
    notify: true,
  },
  xhs: {
    enabled: false,
    crawlerType: 'creator',
    targetValue: '',
    riskWords: defaultRiskWords,
    loginType: 'qrcode',
    cookies: '',
    headless: false,
    interval: 'hourly',
    maxNotesMode: 'limit',
    maxNotes: 20,
    maxCommentsMode: 'limit',
    maxComments: 50,
    includeSubComments: false,
    notify: true,
  },
  bili: {
    enabled: false,
    crawlerType: 'creator',
    targetValue: '',
    riskWords: defaultRiskWords,
    loginType: 'qrcode',
    cookies: '',
    headless: false,
    interval: 'hourly',
    maxNotesMode: 'limit',
    maxNotes: 20,
    maxCommentsMode: 'limit',
    maxComments: 50,
    includeSubComments: false,
    notify: true,
  },
}

function splitWords(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function targetLabel(type: CrawlerMode) {
  if (type === 'detail') return '视频/笔记链接或 ID'
  if (type === 'creator') return '监控账号'
  return '监控关键词'
}

function targetHint(platform: PlatformKey, type: CrawlerMode) {
  if (type === 'search') return '多个关键词用英文逗号分隔'
  if (platform === 'xhs') return '输入小红书号或主页链接，例如 63566726289'
  if (platform === 'dy') return '输入抖音号、主页链接或 sec_user_id'
  return '输入 B站 UID、UP 主空间链接或主页链接'
}

function accountStatus(config: PlatformConfig, loginStatus?: LoginStatus) {
  if (config.loginType === 'cookie') {
    return config.cookies.trim()
      ? { label: '已配置', color: 'bg-cyber-neon-green', text: 'text-cyber-neon-green', border: 'border-cyber-neon-green/40' }
      : { label: '未登录', color: 'bg-cyber-neon-pink', text: 'text-cyber-neon-pink', border: 'border-cyber-neon-pink/40' }
  }

  if (loginStatus?.status === 'running') {
    return { label: '登录中', color: 'bg-cyber-neon-yellow', text: 'text-cyber-neon-yellow', border: 'border-cyber-neon-yellow/40' }
  }
  if (loginStatus?.status === 'success' || loginStatus?.has_local_state) {
    return { label: '已登录', color: 'bg-cyber-neon-green', text: 'text-cyber-neon-green', border: 'border-cyber-neon-green/40' }
  }
  if (loginStatus?.status === 'error') {
    return { label: '失败', color: 'bg-cyber-neon-pink', text: 'text-cyber-neon-pink', border: 'border-cyber-neon-pink/40' }
  }

  return { label: '未登录', color: 'bg-cyber-neon-pink', text: 'text-cyber-neon-pink', border: 'border-cyber-neon-pink/40' }
}

function normalizeMonitorAccount(platform: PlatformKey, value: string) {
  const trimmed = value.trim()
  if (platform === 'xhs') {
    return knownXhsAccountMap[trimmed] ?? trimmed
  }
  return trimmed
}

function intervalLabel(interval: string) {
  if (interval === 'twice_daily') return '每天两次'
  if (interval === 'daily') return '每天一次'
  return '每小时'
}

function formatDateTime(value?: string | null) {
  if (!value) return '等待运行'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function monitorStatusLabel(job?: MonitorJobStatus) {
  if (!job?.enabled) return '未启用'
  if (job.running || job.last_status === 'running') return '运行中'
  if (job.last_status === 'success') return '运行正常'
  if (job.last_status === 'failed') return '运行失败'
  return '等待运行'
}

type MonitorBadgeVariant = 'default' | 'destructive' | 'success' | 'idle'

function monitorBadgeVariant(job?: MonitorJobStatus): MonitorBadgeVariant {
  if (!job?.enabled) return 'idle'
  if (job.last_status === 'failed') return 'destructive'
  if (job.running || job.last_status === 'success') return 'success'
  return 'default'
}

function AccountConfigDialog({
  platform,
  config,
  loginStatus,
  isStartingLogin,
  onChange,
  onStartLogin,
}: {
  platform: PlatformMeta
  config: PlatformConfig
  loginStatus?: LoginStatus
  isStartingLogin: boolean
  onChange: (config: Partial<PlatformConfig>) => void
  onStartLogin: () => void
}) {
  const isLoginRunning = loginStatus?.status === 'running'
  const hasLoginState = loginStatus?.status === 'success' || loginStatus?.has_local_state
  const loginButtonLabel = isLoginRunning ? '正在验证' : hasLoginState ? '重新验证登录态' : '打开扫码登录'

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <ShieldCheck className="h-4 w-4" />
          配置账号
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{platform.name}账号配置</DialogTitle>
          <DialogDescription>
            评论采集引擎读取评论区需要可用登录态。定时监控建议使用公司授权账号 Cookie；临时测试可以使用扫码或 CDP 登录态。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label className="text-xs text-cyber-text-secondary font-mono">登录方式</Label>
              <Select value={config.loginType} onValueChange={(value: LoginType) => onChange({ loginType: value })}>
                <SelectTrigger className="h-9 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cookie">Cookie</SelectItem>
                  <SelectItem value="qrcode">扫码 / CDP</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <label className="h-[62px] px-3 rounded-md border border-cyber-border-subtle bg-cyber-bg-tertiary/40 flex items-center gap-3 cursor-pointer self-end">
              <Checkbox checked={config.headless} onCheckedChange={(checked) => onChange({ headless: checked === true })} />
              <span className="text-xs text-cyber-text-secondary font-mono">无头运行</span>
            </label>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-cyber-text-secondary font-mono">Cookie</Label>
            <textarea
              value={config.cookies}
              onChange={(event) => onChange({ cookies: event.target.value })}
              placeholder="粘贴该平台 Web Cookie；选择扫码时可留空"
              className="min-h-[130px] w-full rounded-md border border-cyber-border-DEFAULT bg-cyber-bg-tertiary px-3 py-2 text-xs font-mono text-cyber-text-primary placeholder:text-cyber-text-muted focus-visible:outline-none focus-visible:border-cyber-neon-cyan/50 focus-visible:shadow-cyber-soft transition-all resize-none"
            />
          </div>

          {config.loginType === 'qrcode' ? (
            <div className="rounded-md border border-cyber-border-subtle bg-cyber-bg-panel/50 p-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-xs font-mono text-cyber-text-primary">
                  {loginStatus?.status === 'success' || loginStatus?.has_local_state ? (
                    <CheckCircle2 className="h-4 w-4 text-cyber-neon-green" />
                  ) : (
                    <QrCode className="h-4 w-4 text-cyber-neon-cyan" />
                  )}
                  扫码登录态
                </div>
                <p className="mt-1 text-[11px] text-cyber-text-muted">
                  点击后会打开独立浏览器窗口；如果已经登录，会自动验证并保存状态；如果未登录，再扫码完成授权。
                </p>
                {hasLoginState ? (
                  <p className="mt-1 text-[11px] text-cyber-neon-green">
                    已检测到本地登录态，后续评论扫描会直接复用这个账号。
                  </p>
                ) : null}
                {loginStatus?.error_message ? (
                  <p className="mt-1 text-[11px] text-cyber-neon-pink">{loginStatus.error_message}</p>
                ) : null}
              </div>
              <Button size="sm" onClick={onStartLogin} disabled={isStartingLogin || isLoginRunning}>
                {isStartingLogin || isLoginRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <QrCode className="h-4 w-4" />}
                {loginButtonLabel}
              </Button>
            </div>
          ) : null}

          <div className="rounded-md border border-cyber-neon-orange/30 bg-cyber-neon-orange/10 p-3 text-[11px] leading-relaxed text-cyber-neon-orange">
            账号信息只保存在当前页面状态里，用于本地启动评论采集引擎。请使用公司授权账号，并控制采集频率与数量。
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" size="sm">保存配置</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function PlatformPanel({
  platform,
  config,
  loginStatus,
  isStartingLogin,
  onChange,
  onStartLogin,
  onScan,
  onToggleMonitor,
  disabled,
  monitorStatus,
  isTogglingMonitor,
}: {
  platform: PlatformMeta
  config: PlatformConfig
  loginStatus?: LoginStatus
  isStartingLogin: boolean
  onChange: (config: Partial<PlatformConfig>) => void
  onStartLogin: () => void
  onScan: () => void
  onToggleMonitor: () => void
  disabled: boolean
  monitorStatus?: MonitorJobStatus
  isTogglingMonitor: boolean
}) {
  const words = useMemo(() => splitWords(config.riskWords), [config.riskWords])
  const status = accountStatus(config, loginStatus)
  const monitorEnabled = monitorStatus?.enabled ?? config.enabled

  return (
    <section className="rounded-lg glass-panel float-panel overflow-hidden">
      <header className="px-4 py-3 border-b border-cyber-border-subtle/50 bg-cyber-bg-tertiary/30 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-10 w-10 rounded-md border border-cyber-border-subtle bg-cyber-bg-panel/70 flex items-center justify-center overflow-hidden">
            <img src={platform.logo} alt="" className="h-7 w-7 object-contain" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-mono font-semibold text-cyber-text-primary">{platform.name}</h2>
              <Badge variant={monitorBadgeVariant(monitorStatus)}>{monitorStatusLabel(monitorStatus)}</Badge>
            </div>
            <p className="text-[11px] text-cyber-text-muted truncate">{platform.description}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <AccountConfigDialog
            platform={platform}
            config={config}
            loginStatus={loginStatus}
            isStartingLogin={isStartingLogin}
            onChange={onChange}
            onStartLogin={onStartLogin}
          />
          <div
            className={`h-9 px-2.5 rounded-md border ${status.border} bg-cyber-bg-panel/60 flex items-center gap-2`}
            title={`账号登录状态：${status.label}`}
            aria-label={`账号登录状态：${status.label}`}
          >
            <span className={`h-2.5 w-2.5 rounded-full ${status.color} shadow-glow-green-sm`} />
            <span className={`text-[11px] font-mono ${status.text}`}>{status.label}</span>
          </div>
          <Button variant={monitorEnabled ? 'outline' : 'default'} size="sm" onClick={onToggleMonitor} disabled={isTogglingMonitor}>
            {isTogglingMonitor ? <Loader2 className="h-4 w-4 animate-spin" /> : <Settings2 className="h-4 w-4" />}
            {monitorEnabled ? '暂停监控' : '启用监控'}
          </Button>
        </div>
      </header>

      <div className="p-4 grid grid-cols-1 xl:grid-cols-[1.15fr_0.85fr] gap-4">
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3">
            <div className="space-y-2">
              <Label className="text-xs text-cyber-text-secondary font-mono">{targetLabel(config.crawlerType)}</Label>
              <Input
                value={config.targetValue}
                onChange={(event) => onChange({ targetValue: event.target.value })}
                placeholder={targetHint(platform.id, config.crawlerType)}
                className="h-9 text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-2">
              <Label className="text-xs text-cyber-text-secondary font-mono">执行频率</Label>
              <Select value={config.interval} onValueChange={(value) => onChange({ interval: value })}>
                <SelectTrigger className="h-9 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="hourly">每小时</SelectItem>
                  <SelectItem value="twice_daily">每天两次</SelectItem>
                  <SelectItem value="daily">每天一次</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-xs text-cyber-text-secondary font-mono">每次采集量</Label>
              <div className="grid grid-cols-[132px_1fr] gap-2">
                <Select value={config.maxNotesMode} onValueChange={(value: 'limit' | 'all') => onChange({ maxNotesMode: value })}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="limit">设置数量</SelectItem>
                    <SelectItem value="all">全笔记/视频</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  min={1}
                  max={10000}
                  value={config.maxNotes}
                  disabled={config.maxNotesMode === 'all'}
                  onChange={(event) => onChange({ maxNotes: Number(event.target.value) || 1 })}
                  className="h-9 text-xs"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-xs text-cyber-text-secondary font-mono">每条评论数</Label>
              <div className="grid grid-cols-[132px_1fr] gap-2">
                <Select value={config.maxCommentsMode} onValueChange={(value: 'limit' | 'all') => onChange({ maxCommentsMode: value })}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="limit">设置数量</SelectItem>
                    <SelectItem value="all">全评论爬取</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  min={1}
                  max={10000}
                  value={config.maxComments}
                  disabled={config.maxCommentsMode === 'all'}
                  onChange={(event) => onChange({ maxComments: Number(event.target.value) || 1 })}
                  className="h-9 text-xs"
                />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_180px] gap-3">
            <div className="space-y-2">
              <Label className="text-xs text-cyber-text-secondary font-mono">风险词库</Label>
              <Input
                value={config.riskWords}
                onChange={(event) => onChange({ riskWords: event.target.value })}
                placeholder={defaultRiskWords}
                className="h-9 text-xs"
              />
            </div>
            <label className="h-9 px-3 rounded-md border border-cyber-border-subtle bg-cyber-bg-tertiary/30 flex items-center gap-3 cursor-pointer self-end">
              <Checkbox checked={config.includeSubComments} onCheckedChange={(checked) => onChange({ includeSubComments: checked === true })} />
              <span className="text-xs text-cyber-text-secondary font-mono">二级评论</span>
            </label>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {words.slice(0, 16).map((word) => (
              <span
                key={word}
                className="px-2 py-1 rounded-md border border-cyber-neon-orange/30 bg-cyber-neon-orange/10 text-cyber-neon-orange text-[11px] font-mono"
              >
                {word}
              </span>
            ))}
            {words.length > 16 ? (
              <span className="px-2 py-1 rounded-md border border-cyber-border-subtle bg-cyber-bg-tertiary text-cyber-text-muted text-[11px] font-mono">
                +{words.length - 16}
              </span>
            ) : null}
          </div>
        </div>

        <div className="rounded-lg border border-cyber-border-subtle bg-cyber-bg-tertiary/30 p-3 flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-md border border-cyber-border-subtle bg-cyber-bg-panel/60 p-3 min-h-[72px]">
              <div className="flex items-center gap-2 text-[11px] text-cyber-text-muted font-mono">
                <Eye className="h-3.5 w-3.5" />
                最近扫描
              </div>
              <div className="mt-2 text-sm text-cyber-text-primary font-mono">{formatDateTime(monitorStatus?.last_finished_at)}</div>
            </div>
            <div className="rounded-md border border-cyber-border-subtle bg-cyber-bg-panel/60 p-3 min-h-[72px]">
              <div className="flex items-center gap-2 text-[11px] text-cyber-text-muted font-mono">
                <MessageSquareWarning className="h-3.5 w-3.5" />
                下次运行
              </div>
              <div className="mt-2 text-sm text-cyber-neon-orange font-mono">{formatDateTime(monitorStatus?.next_run_at)}</div>
            </div>
          </div>

          <div className="rounded-md border border-cyber-border-subtle bg-cyber-bg-panel/50 p-3 text-[11px] leading-relaxed text-cyber-text-secondary">
            自动任务保存在本机配置文件中。启用后会立刻扫描一次，再按{intervalLabel(config.interval)}继续执行；全部采集会使用较高上限，请控制频率。
            {monitorStatus?.last_error ? <span className="block mt-1 text-cyber-neon-pink">{monitorStatus.last_error}</span> : null}
          </div>

          <label className="h-10 px-3 rounded-md border border-cyber-border-subtle bg-cyber-bg-panel/50 flex items-center gap-3 cursor-pointer">
            <Checkbox checked={config.notify} onCheckedChange={(checked) => onChange({ notify: checked === true })} />
            <BellRing className="h-4 w-4 text-cyber-text-secondary" />
            <span className="text-xs text-cyber-text-secondary font-mono">命中后发送飞书群通知</span>
          </label>

          <div className="flex gap-2 mt-auto">
            <Button className="flex-1" size="sm" onClick={onScan} disabled={disabled}>
              <Play className="h-4 w-4" />
              立即扫描
            </Button>
            <Button variant="outline" size="sm">
              <Bot className="h-4 w-4" />
              规则
            </Button>
          </div>
        </div>
      </div>
    </section>
  )
}

export function CommentManagementPage() {
  const [configs, setConfigs] = useState(initialConfig)
  const [loginStatuses, setLoginStatuses] = useState<Partial<Record<PlatformKey, LoginStatus>>>({})
  const [monitorStatuses, setMonitorStatuses] = useState<Partial<Record<PlatformKey, MonitorJobStatus>>>({})
  const [startingLogin, setStartingLogin] = useState<PlatformKey | null>(null)
  const [togglingMonitor, setTogglingMonitor] = useState<PlatformKey | null>(null)
  const status = useCrawlerStore((state) => state.status)
  const baseCrawlerConfig = useCrawlerStore((state) => state.config)
  const { mutate: startCrawler, isPending } = useStartCrawler()
  const enabledCount = Object.values(monitorStatuses).filter((item) => item?.enabled).length
  const isBusy = isPending || status === 'running' || status === 'stopping'

  const updatePlatform = (platform: PlatformKey, patch: Partial<PlatformConfig>) => {
    setConfigs((current) => ({
      ...current,
      [platform]: {
        ...current[platform],
        ...patch,
      },
    }))
  }

  const refreshLoginStatus = useCallback(async (platform: PlatformKey) => {
    const { data } = await crawlerApi.getLoginStatus(platform)
    setLoginStatuses((current) => ({ ...current, [platform]: data }))
    return data
  }, [])

  const refreshMonitorJobs = useCallback(async () => {
    const { data } = await monitorApi.getJobs()
    const jobs = data.jobs.reduce<Partial<Record<PlatformKey, MonitorJobStatus>>>((result, job) => {
      if (job.platform === 'dy' || job.platform === 'xhs' || job.platform === 'bili') {
        result[job.platform] = job
      }
      return result
    }, {})
    setMonitorStatuses(jobs)
    return jobs
  }, [])

  useEffect(() => {
    platforms.forEach((platform) => {
      refreshLoginStatus(platform.id).catch(() => {
        setLoginStatuses((current) => ({
          ...current,
          [platform.id]: {
            status: 'idle',
            platform: platform.id,
            started_at: null,
            finished_at: null,
            error_message: null,
            has_local_state: false,
          },
        }))
      })
    })
  }, [refreshLoginStatus])

  useEffect(() => {
    refreshMonitorJobs().catch(() => undefined)
    const timer = window.setInterval(() => {
      refreshMonitorJobs().catch(() => undefined)
    }, 5000)
    return () => window.clearInterval(timer)
  }, [refreshMonitorJobs])

  useEffect(() => {
    const hasRunningLogin = Object.values(loginStatuses).some((item) => item?.status === 'running')
    if (!hasRunningLogin) return

    const timer = window.setInterval(() => {
      platforms.forEach((platform) => {
        if (loginStatuses[platform.id]?.status === 'running') {
          refreshLoginStatus(platform.id).then((data) => {
            if (data.status === 'success') {
              toast.success(`${platform.name} 登录态已保存`)
            }
            if (data.status === 'error') {
              toast.error(`${platform.name} 登录失败`)
            }
          }).catch(() => undefined)
        }
      })
    }, 2500)

    return () => window.clearInterval(timer)
  }, [loginStatuses, refreshLoginStatus])

  const startPlatformLogin = async (platform: PlatformMeta) => {
    const config = configs[platform.id]
    setStartingLogin(platform.id)
    setLoginStatuses((current) => ({
      ...current,
      [platform.id]: {
        status: 'running',
        platform: platform.id,
        started_at: new Date().toISOString(),
        finished_at: null,
        error_message: null,
        has_local_state: current[platform.id]?.has_local_state ?? false,
      },
    }))

    try {
      await crawlerApi.startLogin({
        platform: platform.id,
        login_type: config.loginType,
        cookies: config.cookies,
        headless: false,
      })
      toast.success(`${platform.name} 登录验证已启动`)
      await refreshLoginStatus(platform.id)
    } catch (error) {
      const message = error instanceof Error ? error.message : '启动登录失败'
      toast.error(`${platform.name} ${message}`)
      setLoginStatuses((current) => ({
        ...current,
        [platform.id]: {
          status: 'error',
          platform: platform.id,
          started_at: current[platform.id]?.started_at ?? null,
          finished_at: new Date().toISOString(),
          error_message: message,
          has_local_state: current[platform.id]?.has_local_state ?? false,
        },
      }))
    } finally {
      setStartingLogin(null)
    }
  }

  const buildCrawlerConfig = (platform: PlatformMeta) => {
    const config = configs[platform.id]
    if (!config.targetValue.trim()) {
      toast.error(`请先填写${platform.name}监控账号`)
      return null
    }

    return {
      platform: platform.id,
      login_type: config.loginType || baseCrawlerConfig.login_type,
      crawler_type: 'creator',
      keywords: '',
      specified_ids: '',
      creator_ids: normalizeMonitorAccount(platform.id, config.targetValue),
      start_page: 1,
      enable_comments: true,
      enable_sub_comments: config.includeSubComments,
      save_option: 'csv',
      cookies: config.cookies || baseCrawlerConfig.cookies,
      headless: config.headless || baseCrawlerConfig.headless,
      max_notes_count: config.maxNotesMode === 'all' ? allItemsLimit : config.maxNotes,
      max_comments_count: config.maxCommentsMode === 'all' ? allItemsLimit : config.maxComments,
      risk_words: config.riskWords,
      notify: config.notify,
    } satisfies CrawlerConfig
  }

  const scanPlatform = (platform: PlatformMeta) => {
    const crawlerConfig = buildCrawlerConfig(platform)
    if (!crawlerConfig) return

    startCrawler(crawlerConfig)
  }

  const toggleMonitor = async (platform: PlatformMeta) => {
    const currentJob = monitorStatuses[platform.id]
    setTogglingMonitor(platform.id)

    try {
      if (currentJob?.enabled) {
        const { data } = await monitorApi.disableJob(platform.id)
        setMonitorStatuses((current) => ({ ...current, [platform.id]: data }))
        updatePlatform(platform.id, { enabled: false })
        toast.success(`${platform.name} 自动监控已暂停`)
        return
      }

      const crawlerConfig = buildCrawlerConfig(platform)
      if (!crawlerConfig) return

      const { data } = await monitorApi.enableJob(platform.id, configs[platform.id].interval, crawlerConfig, true)
      setMonitorStatuses((current) => ({ ...current, [platform.id]: data }))
      updatePlatform(platform.id, { enabled: true })
      toast.success(`${platform.name} 自动监控已启用，正在执行第一次扫描`)
    } catch (error) {
      const message = error instanceof Error ? error.message : '自动监控操作失败'
      toast.error(`${platform.name} ${message}`)
    } finally {
      setTogglingMonitor(null)
      refreshMonitorJobs().catch(() => undefined)
    }
  }

  return (
    <main className="flex-1 overflow-auto min-h-0 relative z-10">
      <div className="p-4 space-y-4">
        <section className="rounded-lg glass-panel float-panel p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-cyber-neon-orange" />
              <h1 className="text-base font-mono font-semibold text-cyber-text-primary">评论区管理</h1>
              <Badge variant="default">采集引擎</Badge>
            </div>
            <p className="mt-1 text-xs text-cyber-text-muted">
              按账号监控抖音、小红书、Bilibili 的全部作品评论，默认保存全量 CSV，并单独输出风险评论 CSV。
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-cyber-text-secondary">
            <Clock3 className="h-4 w-4 text-cyber-text-muted" />
            <span>{enabledCount} 个平台启用</span>
          </div>
        </section>

        <section className="rounded-lg border border-cyber-border-subtle bg-cyber-bg-tertiary/30 p-4 grid grid-cols-1 lg:grid-cols-4 gap-3 text-xs">
          <div className="font-mono text-cyber-text-primary">评论采集需要：</div>
          <div className="text-cyber-text-secondary">账号：Cookie 或扫码/CDP 登录态</div>
          <div className="text-cyber-text-secondary">目标：监控账号的小红书号、抖音号或 B站 UID/主页</div>
          <div className="text-cyber-text-secondary">规则：作品范围、评论范围、风险词、通知方式</div>
        </section>

        <div className="space-y-4">
          {platforms.map((platform) => (
            <PlatformPanel
              key={platform.id}
              platform={platform}
              config={configs[platform.id]}
              loginStatus={loginStatuses[platform.id]}
              isStartingLogin={startingLogin === platform.id}
              onChange={(patch) => updatePlatform(platform.id, patch)}
              onStartLogin={() => startPlatformLogin(platform)}
              onScan={() => scanPlatform(platform)}
              onToggleMonitor={() => toggleMonitor(platform)}
              disabled={isBusy}
              monitorStatus={monitorStatuses[platform.id]}
              isTogglingMonitor={togglingMonitor === platform.id}
            />
          ))}
        </div>
      </div>
    </main>
  )
}
