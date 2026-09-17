import axios from 'axios'
import { authService } from './auth'
import API_BASE from './apiConfig'

/**
 * Control the piezo buzzer on/off
 * @param {boolean} state - true to turn on, false to turn off
 * @returns {Promise<Object>} Response with status and message
 */
export async function controlBuzzer(state) {
    try {
        const response = await authService.apiCall(`${API_BASE}/buzzer/control/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ state }),
        })

        if (response && typeof response.json === 'function') {
            return await response.json()
        }

        return response?.data || { status: state ? 'on' : 'off', state }
    } catch (error) {
        console.error('Failed to control buzzer:', error)
        return {
            error: 'Failed to control buzzer',
            state: state,
        }
    }
}

/**
 * Get current buzzer status
 * @returns {Promise<Object>} Response with current buzzer status
 */
export async function getBuzzerStatus() {
    try {
        const response = await authService.apiCall(`${API_BASE}/buzzer/status/`)

        if (response && typeof response.json === 'function') {
            return await response.json()
        }

        return response?.data || { status: 'unknown', state: false }
    } catch (error) {
        console.error('Failed to get buzzer status:', error)
        return {
            error: 'Failed to get buzzer status',
            state: false,
        }
    }
}

/**
 * Play a buzzer beep sound (browser-based fallback)
 * Uses Web Audio API to generate a beep if buzzer hardware is unavailable
 * @param {number} duration - Duration in milliseconds (default 200)
 * @param {number} frequency - Frequency in Hz (default 1000 - 1kHz)
 */
export function playBeeperSound(duration = 200, frequency = 1000) {
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)()
        const oscillator = audioContext.createOscillator()
        const gainNode = audioContext.createGain()

        oscillator.connect(gainNode)
        gainNode.connect(audioContext.destination)

        oscillator.frequency.value = frequency
        oscillator.type = 'sine'

        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration / 1000)

        oscillator.start(audioContext.currentTime)
        oscillator.stop(audioContext.currentTime + duration / 1000)
    } catch (error) {
        console.warn('Audio context not available:', error)
    }
}
