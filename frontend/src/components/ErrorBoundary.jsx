import { Component } from 'react';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('UI Error Boundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
          <h1 style={{ color: '#dc2626' }}>Something went wrong.</h1>
          <pre style={{ background: '#f8fafc', padding: '1rem', borderRadius: '8px', overflowX: 'auto', fontSize: '14px' }}>
            {String(this.state.error)}
          </pre>
          <button onClick={() => window.location.reload()} style={{ marginTop: '1rem', padding: '0.75rem 1.25rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
