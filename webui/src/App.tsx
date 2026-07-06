import { useState } from 'react'
import { Toaster } from 'sonner'
import { AppNav, type AppPage } from '@/components/layout/AppNav'
import { Sidebar } from '@/components/layout/Sidebar'
import { MainContent } from '@/components/layout/MainContent'
import { AuthorFooter } from '@/components/layout/AuthorFooter'
import { CrawlerConfigPanel } from '@/components/config/CrawlerConfigPanel'
import { CommentManagementPage } from '@/components/comments/CommentManagementPage'
import { FileCenterPage } from '@/components/files/FileCenterPage'
import { BroadcastSettingsPage } from '@/components/settings/BroadcastSettingsPage'
import { EnvironmentCheck, isEnvChecked } from '@/components/env/EnvironmentCheck'
import { LicenseDisclaimer, isLicenseAccepted } from '@/components/license/LicenseDisclaimer'

function App() {
  // Initialize by checking localStorage if license has been accepted
  const [licenseAccepted, setLicenseAccepted] = useState(() => isLicenseAccepted())
  // Initialize by checking localStorage if env check has passed
  const [envChecked, setEnvChecked] = useState(() => isEnvChecked())
  // State for showing disclaimer manually
  const [showDisclaimer, setShowDisclaimer] = useState(false)
  const [currentPage, setCurrentPage] = useState<AppPage>('crawler')

  const handleEnvCheckComplete = () => {
    setEnvChecked(true)
  }

  const handleLicenseAccept = () => {
    setLicenseAccepted(true)
    setShowDisclaimer(false)
  }

  const handleShowDisclaimer = () => {
    setShowDisclaimer(true)
  }

  return (
    <div className="flex flex-col h-screen cyber-grid overflow-hidden relative">
      {/* License Disclaimer Modal - Shows first or when triggered */}
      {(!licenseAccepted || showDisclaimer) && (
        <LicenseDisclaimer onAccept={handleLicenseAccept} />
      )}

      {/* Environment Check Modal - Shows after license accepted */}
      {licenseAccepted && !showDisclaimer && !envChecked && (
        <EnvironmentCheck onCheckComplete={handleEnvCheckComplete} />
      )}

      {/* Header Bar */}
      <Sidebar onShowDisclaimer={handleShowDisclaimer} />

      <div className="flex-1 flex overflow-hidden min-h-0">
        <AppNav currentPage={currentPage} onPageChange={setCurrentPage} />

        {/* Main Area */}
        {currentPage === 'crawler' ? (
          <div className="flex-1 flex flex-col gap-4 p-4 overflow-hidden min-h-0">
            {/* Config Panel - Primary Action Area (Always Expanded) */}
            <div className="flex-shrink-0">
              <CrawlerConfigPanel />
            </div>

            {/* Console - Collapsible Terminal */}
            <MainContent />
          </div>
        ) : currentPage === 'comments' ? (
          <CommentManagementPage />
        ) : currentPage === 'files' ? (
          <FileCenterPage />
        ) : (
          <BroadcastSettingsPage />
        )}
      </div>

      {/* Author Footer */}
      <AuthorFooter />

      {/* Toast notifications - Theme-aware style */}
      <Toaster
        position="top-right"
        toastOptions={{
          className: 'glass-panel font-mono text-cyber-text-primary',
          style: {
            fontFamily: 'JetBrains Mono, monospace',
          },
        }}
      />
    </div>
  )
}

export default App
