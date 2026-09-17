import { useLanguage } from '../context/LanguageContext'

const About = () => {
  const { t } = useLanguage()

  const features = [
    {
      icon: '🌡️',
      title: t('realTimeMonitoring'),
      description: t('realTimeMonitoringDesc')
    },
    {
      icon: '🌤️',
      title: t('weatherIntegration'),
      description: t('weatherIntegrationDesc')
    },
    {
      icon: '📊',
      title: t('advancedAnalytics'),
      description: t('advancedAnalyticsDesc')
    },
    {
      icon: '⚠️',
      title: t('smartAlerts'),
      description: t('smartAlertsDesc')
    },
    {
      icon: '📱',
      title: t('responsiveDesign'),
      description: t('responsiveDesignDesc')
    },
    {
      icon: '🔧',
      title: t('easyManagement'),
      description: t('easyManagementDesc')
    }
  ]

  const developers = [
    {
      name: 'Clifford A. Punzalan',
      role: t('leadDeveloper'),
      description: t('leadDevDesc')
    },
    {
      name: 'Kyla Mariz Tolentino',
      role: t('uiUxDesigner'),
      description: t('uiUxDesc')
    },
    {
      name: 'Dan Icalla',
      role: t('systemArchitect'),
      description: t('systemArchitectDesc')
    }
  ]

  const technologies = [
    { name: 'React', version: '19.1.1', description: 'Frontend framework for building user interfaces' },
    { name: 'React Router', version: '6.x', description: 'Client-side routing for single-page applications' },
    { name: 'Tailwind CSS', version: '3.x', description: 'Utility-first CSS framework for rapid UI development' },
    { name: 'Chart.js', version: '4.x', description: 'JavaScript charting library for data visualization' },
    { name: 'Vite', version: '7.x', description: 'Fast build tool and development server' }
  ]

  const objectives = [
    { title: t('objective1Title'), description: t('objective1Desc') },
    { title: t('objective2Title'), description: t('objective2Desc') },
    { title: t('objective3Title'), description: t('objective3Desc') },
    { title: t('objective4Title'), description: t('objective4Desc') },
    { title: t('objective5Title'), description: t('objective5Desc') },
  ]

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('aboutTheSystem')}</h1>
        <p className="text-gray-600">{t('aboutSubtitle')}</p>
      </div>

      {/* Project Overview */}
      <div className="card-gradient mb-8">
        <div className="text-center mb-8">
          <div className="text-6xl mb-4">🦐</div>
          <h2 className="text-3xl font-bold text-gray-900 mb-4">
            {t('smartShrimpPondSystem')}
          </h2>
          <p className="text-lg text-gray-600 max-w-3xl mx-auto">
            {t('aboutDescription')}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
          <div className="p-6 bg-white bg-opacity-50 rounded-lg">
            <div className="text-3xl font-bold text-primary-600 mb-2">24/7</div>
            <div className="text-gray-700">{t('continuousMonitoring')}</div>
          </div>
          <div className="p-6 bg-white bg-opacity-50 rounded-lg">
            <div className="text-3xl font-bold text-primary-600 mb-2">{t('realTime')}</div>
            <div className="text-gray-700">{t('dataUpdates')}</div>
          </div>
          <div className="p-6 bg-white bg-opacity-50 rounded-lg">
            <div className="text-3xl font-bold text-primary-600 mb-2">{t('smart')}</div>
            <div className="text-gray-700">{t('weatherIntegration')}</div>
          </div>
        </div>
      </div>

      {/* Project Objectives */}
      <div className="mb-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">{t('objectivesTitle')}</h2>
          <p className="text-gray-600 max-w-3xl">{t('objectivesSubtitle')}</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {objectives.map((objective, index) => (
            <div key={index} className="card border border-primary-100 bg-gradient-to-br from-white to-sky-50 hover:shadow-xl transition-shadow duration-300">
              <div className="w-12 h-12 rounded-xl bg-primary-600 text-white flex items-center justify-center font-bold mb-4">
                0{index + 1}
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{objective.title}</h3>
              <p className="text-gray-600 leading-relaxed">{objective.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Features */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">{t('keyFeatures')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <div key={index} className="card hover:shadow-xl transition-shadow duration-300">
              <div className="text-4xl mb-4">{feature.icon}</div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">{feature.title}</h3>
              <p className="text-gray-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Development Team */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">{t('developmentTeam')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {developers.map((developer, index) => (
            <div key={index} className="card text-center">
              <div className="w-20 h-20 bg-gradient-to-r from-primary-500 to-primary-600 rounded-full mx-auto mb-4 flex items-center justify-center">
                <span className="text-2xl text-white font-bold">
                  {developer.name.split(' ').map(n => n[0]).join('')}
                </span>
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-1">{developer.name}</h3>
              <p className="text-primary-600 font-medium mb-2">{developer.role}</p>
              <p className="text-gray-600 text-sm">{developer.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Technology Stack */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">{t('technologyStack')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {technologies.map((tech, index) => (
            <div key={index} className="card">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-semibold text-gray-900">{tech.name}</h3>
                <span className="text-sm text-gray-500">{tech.version}</span>
              </div>
              <p className="text-sm text-gray-600">{tech.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* System Information */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('systemSpecifications')}</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">{t('version')}:</span>
              <span className="font-medium">1.0.0</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">{t('lastUpdated')}:</span>
              <span className="font-medium">{new Date().toLocaleDateString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">{t('dataUpdateFrequency')}:</span>
              <span className="font-medium">2-3 seconds</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">{t('supportedBrowsers')}:</span>
              <span className="font-medium">Chrome, Firefox, Safari, Edge</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">{t('mobileSupport')}:</span>
              <span className="font-medium">{t('yes')}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('contactInformation')}</h3>
          <div className="space-y-3">
            <div className="flex items-center">
              <span className="text-2xl mr-3">📧</span>
              <div>
                <div className="font-medium">{t('emailSupport')}</div>
                <div className="text-sm text-gray-600">support@smartshrimppond.com</div>
              </div>
            </div>
            <div className="flex items-center">
              <span className="text-2xl mr-3">📱</span>
              <div>
                <div className="font-medium">{t('phoneSupport')}</div>
                <div className="text-sm text-gray-600">+63 (XXX) XXX-XXXX</div>
              </div>
            </div>
            <div className="flex items-center">
              <span className="text-2xl mr-3">🌐</span>
              <div>
                <div className="font-medium">{t('website')}</div>
                <div className="text-sm text-gray-600">www.smartshrimppond.com</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="card text-center">
        <div className="text-4xl mb-4">🦐</div>
        <h3 className="text-xl font-semibold text-gray-900 mb-2">
          {t('smartShrimpPondSystem')}
        </h3>
        <p className="text-gray-600 mb-4">
          {t('revolutionizing')}
        </p>
        <div className="text-sm text-gray-500">
          © 2024 Clifford A. Punzalan, Kyla Mariz Tolentino, and Dan Icalla. {t('allRightsReserved')}
        </div>
      </div>
    </div>
  )
}

export default About
