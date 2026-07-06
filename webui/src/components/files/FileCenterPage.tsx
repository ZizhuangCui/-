import { FileSpreadsheet, FolderOpen } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { DataExplorer } from '@/components/data/DataExplorer'

export function FileCenterPage() {
  return (
    <main className="flex-1 overflow-auto min-h-0 relative z-10">
      <div className="p-4 space-y-4 min-h-full">
        <section className="rounded-lg glass-panel float-panel p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <FolderOpen className="h-4 w-4 text-cyber-neon-cyan" />
              <h1 className="text-base font-mono font-semibold text-cyber-text-primary">文件中心</h1>
              <Badge variant="default">CSV / Sheet</Badge>
            </div>
            <p className="mt-1 text-xs text-cyber-text-muted">
              查看采集结果、风险评论、每日汇总和后续同步表格文件；可预览、下载或定位到本地文件夹。
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-cyber-text-secondary">
            <FileSpreadsheet className="h-4 w-4 text-cyber-text-muted" />
            <span>本地 data 目录</span>
          </div>
        </section>

        <section className="rounded-lg glass-panel float-panel p-4 min-h-[calc(100vh-220px)]">
          <DataExplorer />
        </section>
      </div>
    </main>
  )
}
