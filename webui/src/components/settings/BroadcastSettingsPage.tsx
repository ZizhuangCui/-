import { useEffect, useMemo, useState } from 'react'
import { BellRing, FileSpreadsheet, Loader2, MessageSquareText, Save, Settings2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { settingsApi, type BroadcastSettings } from '@/lib/api'

const defaultSettings: BroadcastSettings = {
  enabled: true,
  feishu_group_name: '评论风险监控群',
  period_mode: 'crawl_cycle',
  custom_interval_minutes: 60,
  selected_files: ['daily_summary', 'risk_comments'],
}

const fileOptions: Array<{ value: BroadcastSettings['selected_files'][number]; label: string; description: string }> = [
  {
    value: 'daily_summary',
    label: '每日评论汇总',
    description: '风险词、高赞、点赞增长的统一汇总',
  },
  {
    value: 'risk_comments',
    label: '风险评论',
    description: '只包含命中风险词的评论',
  },
  {
    value: 'raw_comments',
    label: '原始评论全量',
    description: '采集到的全部评论明细',
  },
]

export function BroadcastSettingsPage() {
  const [settings, setSettings] = useState<BroadcastSettings>(defaultSettings)
  const [previewText, setPreviewText] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const selectedSet = useMemo(() => new Set(settings.selected_files), [settings.selected_files])

  useEffect(() => {
    settingsApi.getBroadcast()
      .then(({ data }) => setSettings(data))
      .catch(() => toast.error('读取播报配置失败'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    settingsApi.previewBroadcast(settings)
      .then(({ data }) => setPreviewText(data.text))
      .catch(() => setPreviewText('预览生成失败'))
  }, [settings])

  const updateSettings = (patch: Partial<BroadcastSettings>) => {
    setSettings((current) => ({ ...current, ...patch }))
  }

  const toggleFile = (file: BroadcastSettings['selected_files'][number], checked: boolean) => {
    const next = new Set(settings.selected_files)
    if (checked) {
      next.add(file)
    } else {
      next.delete(file)
    }
    updateSettings({ selected_files: Array.from(next) })
  }

  const save = async () => {
    setSaving(true)
    try {
      const { data } = await settingsApi.saveBroadcast(settings)
      setSettings(data)
      toast.success('飞书播报配置已保存')
    } catch {
      toast.error('保存播报配置失败')
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="flex-1 overflow-auto min-h-0 relative z-10">
      <div className="p-4 space-y-4 min-h-full">
        <section className="rounded-lg glass-panel float-panel p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <BellRing className="h-4 w-4 text-cyber-neon-cyan" />
              <h1 className="text-base font-mono font-semibold text-cyber-text-primary">播报配置</h1>
              <Badge variant={settings.enabled ? 'success' : 'idle'}>{settings.enabled ? '已开启' : '已关闭'}</Badge>
            </div>
            <p className="mt-1 text-xs text-cyber-text-muted">
              配置飞书群机器人摘要播报、播报周期、关联文件和最终消息文本。
            </p>
          </div>
          <Button size="sm" onClick={save} disabled={saving || loading}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            保存配置
          </Button>
        </section>

        <div className="grid grid-cols-1 xl:grid-cols-[0.95fr_1.05fr] gap-4">
          <section className="rounded-lg glass-panel float-panel p-4 space-y-4">
            <div className="flex items-center gap-2 text-sm font-mono font-semibold text-cyber-text-primary">
              <Settings2 className="h-4 w-4 text-cyber-neon-cyan" />
              基础设置
            </div>

            <label className="h-12 px-3 rounded-md border border-cyber-border-subtle bg-cyber-bg-tertiary/30 flex items-center gap-3 cursor-pointer">
              <Checkbox checked={settings.enabled} onCheckedChange={(checked) => updateSettings({ enabled: checked })} />
              <span className="text-xs text-cyber-text-secondary font-mono">开启飞书群机器人播报</span>
            </label>

            <div className="space-y-2">
              <Label className="text-xs text-cyber-text-secondary font-mono">飞书群名称</Label>
              <Input
                value={settings.feishu_group_name}
                onChange={(event) => updateSettings({ feishu_group_name: event.target.value })}
                placeholder="评论风险监控群"
                className="h-9 text-xs"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label className="text-xs text-cyber-text-secondary font-mono">播报周期</Label>
                <Select value={settings.period_mode} onValueChange={(value: BroadcastSettings['period_mode']) => updateSettings({ period_mode: value })}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="crawl_cycle">按爬取周期</SelectItem>
                    <SelectItem value="custom">自定义周期</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-cyber-text-secondary font-mono">自定义周期（分钟）</Label>
                <Input
                  type="number"
                  min={5}
                  max={1440}
                  value={settings.custom_interval_minutes}
                  disabled={settings.period_mode !== 'custom'}
                  onChange={(event) => updateSettings({ custom_interval_minutes: Number(event.target.value) || 60 })}
                  className="h-9 text-xs"
                />
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-mono font-semibold text-cyber-text-primary">
                <FileSpreadsheet className="h-4 w-4 text-cyber-neon-green" />
                播报文件
              </div>
              {fileOptions.map((file) => (
                <label key={file.value} className="min-h-[58px] px-3 py-2 rounded-md border border-cyber-border-subtle bg-cyber-bg-tertiary/30 flex items-start gap-3 cursor-pointer">
                  <div className="pt-1">
                    <Checkbox checked={selectedSet.has(file.value)} onCheckedChange={(checked) => toggleFile(file.value, checked)} />
                  </div>
                  <span className="min-w-0">
                    <span className="block text-xs font-mono text-cyber-text-primary">{file.label}</span>
                    <span className="block text-[11px] text-cyber-text-muted mt-1">{file.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </section>

          <section className="rounded-lg glass-panel float-panel p-4 flex flex-col min-h-[520px]">
            <div className="flex items-center gap-2 text-sm font-mono font-semibold text-cyber-text-primary">
              <MessageSquareText className="h-4 w-4 text-cyber-neon-cyan" />
              播报文本预览
            </div>
            <div className="mt-4 flex-1 rounded-md border border-cyber-border-subtle bg-cyber-bg-panel/70 p-4">
              <pre className="whitespace-pre-wrap text-xs leading-relaxed text-cyber-text-primary font-mono">{previewText}</pre>
            </div>
            <p className="mt-3 text-[11px] text-cyber-text-muted">
              预览使用示例数据；真实播报会使用每次扫描后新增的高亮评论。
            </p>
          </section>
        </div>
      </div>
    </main>
  )
}
