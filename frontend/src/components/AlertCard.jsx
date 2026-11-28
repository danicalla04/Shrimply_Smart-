import { usePrivileges } from '../context/PrivilegesContext'
import CloseButton from './CloseButton'
import { useLanguage } from '../context/LanguageContext'

function formatStoredAlertAge(message) {
  // Older saved alerts contain a fixed age in seconds. Keep them readable too.
  return String(message || '').replace(/\((\d+)s ago\)/g, (_, value) => {
    const seconds = Number(value)
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (days) return `(${days}d${hours ? ` ${hours}hr` : ''} ago)`
    if (hours) return `(${hours}hr${minutes ? ` ${minutes}min` : ''} ago)`
    if (minutes) return `(${minutes}min ago)`
    return `(${seconds}s ago)`
  })
}

const AlertCard = ({ title, message, type, timestamp, isRead, onMarkAsRead, onDismiss }) => {
  const { t } = useLanguage()
  const privileges = usePrivileges()
  const alertClasses = {
    critical: 'alert-critical',
    warning: 'alert-warning',
    safe: 'alert-safe'
  }

  const iconClasses = {
    critical: '🔴',
    warning: '🟡',
    safe: '🟢'
  }

  return (
    <div className={`card alert-card ${alertClasses[type] || ''} ${isRead ? 'is-read' : ''}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3">
          <span className="text-2xl">{iconClasses[type]}</span>
          <div className="flex-1">
            <h3 className="font-semibold text-lg mb-1">{title}</h3>
            <p className="text-sm mb-2">{formatStoredAlertAge(message)}</p>
            <p className="text-xs opacity-75">{timestamp}</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {!isRead && (
            <button
              disabled={!privileges.update} onClick={onMarkAsRead}
              className="btn-secondary text-xs px-3 py-1"
            >
              {t('markAsRead')}
            </button>
          )}
          {privileges.delete && <CloseButton
            onClick={onDismiss}
            size="md"
            variant="default"
  q           title="Delete"
          />}
        </div>
      </div>
    </div>
  )
}

export default AlertCard
