import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { FolderOpen, RefreshCw } from 'lucide-react'
import { dataApi } from '@/lib/api'
import { FileCard } from './FileCard'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

// 从文件名提取类别
function extractCategory(filename: string): string {
  // 文件名格式: search_comments_xxx, search_creators_xxx, search_videos_xxx 等
  const match = filename.match(/^(search_\w+?)_/)
  if (match) {
    return match[1]
  }
  // 其他格式尝试提取前缀
  const parts = filename.split('_')
  if (parts.length >= 2) {
    return `${parts[0]}_${parts[1]}`
  }
  return 'other'
}

// 类别显示名称
function getCategoryLabel(category: string): string {
  const labels: Record<string, string> = {
    'daily_summary': '每日汇总',
    'risk_comments': '风险评论',
    'raw_comments': '原始评论',
    'raw_contents': '原始作品',
    'search_comments': 'Comments',
    'search_creators': 'Creators',
    'search_videos': 'Videos',
    'search_contents': 'Contents',
    'search_notes': 'Notes',
    'other': 'Other',
  }
  return labels[category] || category.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export function DataExplorer() {
  const { t } = useTranslation('data')
  const [activeTab, setActiveTab] = useState<string>('all')
  const [activePlatform, setActivePlatform] = useState<string>('all')

  const { data, isLoading, refetch, isRefetching } = useQuery({
    queryKey: ['dataFiles'],
    queryFn: async () => {
      const { data } = await dataApi.getFiles()
      return data.files
    },
  })

  const files = data || []

  const platformOptions = useMemo(() => {
    const options = new Map<string, string>()
    files.forEach((file) => {
      if (file.platform && file.platform_label && file.platform !== 'reports') {
        options.set(file.platform, file.platform_label)
      }
    })
    return Array.from(options.entries()).sort((a, b) => a[1].localeCompare(b[1], 'zh-CN'))
  }, [files])

  const platformFilteredFiles = useMemo(() => {
    if (activePlatform === 'all') return files
    return files.filter((file) => file.platform === activePlatform)
  }, [activePlatform, files])

  // 按类别分组文件
  const { categories, groupedFiles } = useMemo(() => {
    const grouped: Record<string, typeof files> = {}

    platformFilteredFiles.forEach(file => {
      const category = file.category || extractCategory(file.name)
      if (!grouped[category]) {
        grouped[category] = []
      }
      grouped[category].push(file)
    })

    // 按文件数量排序类别
    const sortedCategories = Object.keys(grouped).sort((a, b) =>
      grouped[b].length - grouped[a].length
    )

    return { categories: sortedCategories, groupedFiles: grouped }
  }, [platformFilteredFiles])

  // 当前显示的文件
  const displayFiles = activeTab === 'all' ? platformFilteredFiles : (groupedFiles[activeTab] || [])

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-mono font-bold text-cyber-neon-cyan glow-text-cyan tracking-wider">
            {t('explorer.title')}
          </h2>
          <Badge variant="default" className="font-mono">
            {t('explorer.records', { count: files.length })}
          </Badge>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isRefetching}
          className="font-mono"
        >
          <RefreshCw className={`w-4 h-4 ${isRefetching ? 'animate-spin' : ''}`} />
          {t('explorer.rescan')}
        </Button>
      </div>

      {/* Category Tabs */}
      {files.length > 0 && (
        <div className="flex flex-col gap-3 mb-4">
          {platformOptions.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-cyber-text-muted font-mono">平台</span>
              <button
                onClick={() => setActivePlatform('all')}
                className={`px-3 py-1.5 rounded-md text-xs font-mono transition-all ${
                  activePlatform === 'all'
                    ? 'bg-cyber-neon-green text-black font-bold'
                    : 'bg-cyber-bg-tertiary text-cyber-text-secondary hover:text-cyber-text-primary border border-cyber-border-subtle hover:border-cyber-neon-green/50'
                }`}
              >
                全部平台 ({files.length})
              </button>
              {platformOptions.map(([platform, label]) => {
                const count = files.filter((file) => file.platform === platform).length
                return (
                  <button
                    key={platform}
                    onClick={() => setActivePlatform(platform)}
                    className={`px-3 py-1.5 rounded-md text-xs font-mono transition-all ${
                      activePlatform === platform
                        ? 'bg-cyber-neon-green text-black font-bold'
                        : 'bg-cyber-bg-tertiary text-cyber-text-secondary hover:text-cyber-text-primary border border-cyber-border-subtle hover:border-cyber-neon-green/50'
                    }`}
                  >
                    {label} ({count})
                  </button>
                )
              })}
            </div>
          )}

          {categories.length > 1 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-cyber-text-muted font-mono">文件</span>
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1.5 rounded-md text-xs font-mono transition-all ${
              activeTab === 'all'
                ? 'bg-cyber-neon-cyan text-black font-bold'
                : 'bg-cyber-bg-tertiary text-cyber-text-secondary hover:text-cyber-text-primary border border-cyber-border-subtle hover:border-cyber-neon-cyan/50'
            }`}
          >
            {t('explorer.allCategories')} ({platformFilteredFiles.length})
          </button>
          {categories.map(category => (
            <button
              key={category}
              onClick={() => setActiveTab(category)}
              className={`px-3 py-1.5 rounded-md text-xs font-mono transition-all ${
                activeTab === category
                  ? 'bg-cyber-neon-cyan text-black font-bold'
                  : 'bg-cyber-bg-tertiary text-cyber-text-secondary hover:text-cyber-text-primary border border-cyber-border-subtle hover:border-cyber-neon-cyan/50'
              }`}
            >
            {getCategoryLabel(category)} ({groupedFiles[category].length})
            </button>
          ))}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-cyber-text-muted font-mono animate-pulse">
            {t('explorer.loading')}
          </div>
        </div>
      ) : files.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center">
          <div className="relative">
            <FolderOpen className="w-16 h-16 text-cyber-neon-cyan/30 mb-4" />
            <div className="absolute inset-0 blur-xl bg-cyber-neon-cyan/10" />
          </div>
          <h3 className="text-lg font-mono font-medium text-cyber-neon-cyan mb-2">
            {t('explorer.noData')}
          </h3>
          <p className="text-sm text-cyber-text-muted max-w-md font-mono">
            {t('explorer.noDataHint')}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {displayFiles.map((file) => (
            <FileCard key={file.path} file={file} />
          ))}
        </div>
      )}
    </div>
  )
}
