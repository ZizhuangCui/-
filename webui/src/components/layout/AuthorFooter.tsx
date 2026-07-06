import { useTranslation } from 'react-i18next'
import { ShieldCheck, Heart } from 'lucide-react'

export function AuthorFooter() {
  const { t } = useTranslation('license')

  return (
    <footer className="h-24 flex-shrink-0 glass-panel border-t border-cyber-border-subtle">
      <div className="h-full px-6 flex items-center justify-center gap-6">
        {/* Product mark */}
        <div className="w-14 h-14 rounded-lg border-2 border-cyber-neon-cyan/60 flex-shrink-0 shadow-glow-cyan-sm flex items-center justify-center bg-cyber-bg-tertiary">
          <ShieldCheck className="w-8 h-8 text-cyber-neon-cyan" />
        </div>

        {/* Product Info */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-cyber-text-primary">
              {t('author.name')}
            </span>
            <ShieldCheck className="w-5 h-5 text-cyber-neon-cyan animate-pulse" />
          </div>
          <span className="text-sm text-cyber-text-muted hidden sm:inline">
            {t('author.description')}
          </span>
          <div className="flex items-center gap-2 text-cyber-neon-cyan">
            <Heart className="w-4 h-4 fill-current animate-pulse" />
            <span className="text-sm font-medium">
              {t('author.slogan')}
            </span>
          </div>
        </div>
      </div>
    </footer>
  )
}
