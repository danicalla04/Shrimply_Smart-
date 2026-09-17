import CloseButton from './CloseButton'
import { useLanguage } from '../context/LanguageContext'

const AlertCard = ({ title, message, type, timestamp, isRead, onMarkAsRead, onDismiss }) => {
  const { t } = useLanguage()
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
    <div className={`alert-card ${alertClasses[type]} ${isRead ? 'opacity-60' : ''}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-3">
          <span className="text-2xl">{iconClasses[type]}</span>
          <div className="flex-1">
            <h3 className="font-semibold text-lg mb-1">{title}</h3>
            <p className="text-sm mb-2">{message}</p>
            <p className="text-xs opacity-75">{timestamp}</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {!isRead && (
            <button
              onClick={onMarkAsRead}
              className="btn-secondary text-xs px-3 py-1"
            >
              {t('markAsRead')}
            </button>
          )}
          <CloseButton
            onClick={onDismiss}
            size="md"
            variant="default"
          />
        </div>
      </div>
    </div>
  )
}

export default AlertCard
