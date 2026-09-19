import { useEffect } from 'react'

let loaderCount = 0

function bootEl() {
  return document.getElementById('boot-loader')
}

function ensureBootLoader(label) {
  let el = bootEl()
  if (!el) {
    el = document.createElement('div')
    el.id = 'boot-loader'
    el.className = 'page-loader'
    el.setAttribute('role', 'status')
    el.setAttribute('aria-live', 'polite')
    el.setAttribute('aria-label', 'Loading')
    el.innerHTML = `
      <div class="page-loader-mark"><img src="/shrimply-logo.jpg" alt="" /></div>
      <div class="page-loader-name"></div>
    `
    document.body.appendChild(el)
  }
  const name = el.querySelector('.page-loader-name')
  if (name) name.textContent = label || 'Shrimply Smart'
  el.classList.remove('is-off')
  return el
}

export function hideBootIfIdle() {
  if (loaderCount > 0) return
  const el = bootEl()
  if (el) el.classList.add('is-off')
  document.body.classList.remove('aq-loading')
}

export default function PageLoader({ label = 'Shrimply Smart' }) {
  useEffect(() => {
    loaderCount += 1
    document.body.classList.add('aq-loading')
    ensureBootLoader(label)
    return () => {
      loaderCount = Math.max(0, loaderCount - 1)
      if (loaderCount === 0) hideBootIfIdle()
    }
  }, [label])

  return null
}
