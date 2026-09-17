const CloseButton = ({ onClick, size = 'md', variant = 'default', className = '' }) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
    lg: 'w-6 h-6',
    xl: 'w-8 h-8'
  }

  const variantClasses = {
    default: 'text-gray-400 hover:text-red-500',
    danger: 'text-red-400 hover:text-red-600',
    light: 'text-gray-300 hover:text-gray-500',
    dark: 'text-gray-600 hover:text-gray-800'
  }

  return (
    <button
      onClick={onClick}
      className={`dismiss-btn ${variantClasses[variant]} ${className}`}
      title="Close"
    >
      <svg className={sizeClasses[size]} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  )
}

export default CloseButton
