import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail
      const message = Array.isArray(detail)
        ? detail.map((item) => item?.msg ?? String(item)).join('；')
        : typeof detail === 'string'
          ? detail
          : error.response?.status
            ? `请求失败，状态码 ${error.response.status}`
            : error.message
      return Promise.reject(new Error(message))
    }

    return Promise.reject(error)
  },
)

// Types
export interface CrawlerConfig {
  platform: string
  login_type: string
  crawler_type: string
  keywords: string
  specified_ids: string
  creator_ids: string
  start_page: number
  enable_comments: boolean
  enable_sub_comments: boolean
  save_option: string
  cookies: string
  headless: boolean
  max_notes_count?: number
  max_comments_count?: number
  risk_words?: string
  notify?: boolean
}

export interface CrawlerStatus {
  status: 'idle' | 'running' | 'stopping' | 'error'
  platform: string | null
  crawler_type: string | null
  started_at: string | null
  error_message: string | null
}

export interface LoginStartRequest {
  platform: string
  login_type: string
  cookies: string
  headless: boolean
}

export interface LoginStatus {
  status: 'idle' | 'running' | 'success' | 'error'
  platform: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  has_local_state: boolean
}

export interface MonitorJobStatus {
  platform: string
  enabled: boolean
  interval: 'hourly' | 'twice_daily' | 'daily'
  config: CrawlerConfig | null
  next_run_at: string | null
  last_run_at: string | null
  last_finished_at: string | null
  last_status: 'idle' | 'running' | 'success' | 'failed' | 'skipped'
  last_error: string | null
  running: boolean
}

export interface BroadcastSettings {
  enabled: boolean
  feishu_group_name: string
  period_mode: 'crawl_cycle' | 'custom'
  custom_interval_minutes: number
  selected_files: Array<'daily_summary' | 'risk_comments' | 'raw_comments'>
}

export interface LogEntry {
  id: number
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success' | 'debug'
  message: string
}

export interface DataFile {
  name: string
  display_name?: string
  platform?: string
  platform_label?: string
  category?: string
  category_label?: string
  description?: string
  path: string
  size: number
  modified_at: number
  record_count: number | null
  type: string
}

export interface FilePreviewResponse {
  data: Record<string, unknown>[]
  total: number
  columns?: string[]
}

export interface Platform {
  value: string
  label: string
  icon: string
}

export interface ConfigOption {
  value: string
  label: string
}

// API functions
export const crawlerApi = {
  start: (config: CrawlerConfig) => api.post('/crawler/start', config),
  stop: () => api.post('/crawler/stop'),
  getStatus: () => api.get<CrawlerStatus>('/crawler/status'),
  getLogs: (limit = 100) => api.get<{ logs: LogEntry[] }>('/crawler/logs', { params: { limit } }),
  startLogin: (request: LoginStartRequest) => api.post('/crawler/login/start', request),
  getLoginStatus: (platform: string) => api.get<LoginStatus>(`/crawler/login/status/${platform}`),
}

export const monitorApi = {
  getJobs: () => api.get<{ jobs: MonitorJobStatus[] }>('/monitor/jobs'),
  getJob: (platform: string) => api.get<MonitorJobStatus>(`/monitor/jobs/${platform}`),
  enableJob: (platform: string, interval: string, config: CrawlerConfig, runImmediately = true) =>
    api.post<MonitorJobStatus>(`/monitor/jobs/${platform}/enable`, {
      platform,
      interval,
      config,
      run_immediately: runImmediately,
    }),
  disableJob: (platform: string) => api.post<MonitorJobStatus>(`/monitor/jobs/${platform}/disable`),
}

export const dataApi = {
  getFiles: (platform?: string, fileType?: string) =>
    api.get<{ files: DataFile[] }>('/data/files', { params: { platform, file_type: fileType } }),
  getFileContent: (path: string, limit = 100) =>
    api.get<FilePreviewResponse>('/data/files/' + path, { params: { preview: true, limit } }),
  getStats: () => api.get('/data/stats'),
  getDownloadUrl: (path: string) => `/api/data/download/${path}`,
  revealFile: (path: string) => api.post('/data/reveal/' + path),
}

export const settingsApi = {
  getBroadcast: () => api.get<BroadcastSettings>('/settings/broadcast'),
  saveBroadcast: (settings: BroadcastSettings) => api.put<BroadcastSettings>('/settings/broadcast', settings),
  previewBroadcast: (settings: BroadcastSettings) => api.post<{ text: string }>('/settings/broadcast/preview', settings),
}

export const configApi = {
  getPlatforms: () => api.get<{ platforms: Platform[] }>('/config/platforms'),
  getOptions: () =>
    api.get<{
      login_types: ConfigOption[]
      crawler_types: ConfigOption[]
      save_options: ConfigOption[]
    }>('/config/options'),
}

export interface EnvCheckResult {
  success: boolean
  message: string
  output?: string
  error?: string
}

export const envApi = {
  check: () => api.get<EnvCheckResult>('/env/check', { timeout: 45000 }),
}

export default api
