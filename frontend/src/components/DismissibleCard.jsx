import { useState } from 'react'
import CloseButton from './CloseButton'

const DismissibleCard = ({ children, onDismiss, className = '' }) => {
  const [isVisible, setIsVisible] = useState(true)

  const handleDismiss = () => {
    setIsVisible(false)
    if (onDismiss) {
      onDismiss()
    }
  }

  if (!isVisible) {
    return null
  }

  return (
    <div className={`card relative ${className}`}>
      <CloseButton
        onClick={handleDismiss}
        size="sm"
        variant="light"
        className="absolute top-2 right-2"
      />
      {children}
    </div>
  )
}

export default DismissibleCard
