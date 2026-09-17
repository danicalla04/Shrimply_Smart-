import API_BASE from './apiConfig'
const API_URL = API_BASE

/**
 * Fetch current water quality status for shrimp farming
 * @returns {Promise} Water quality assessment data
 */
export const getWaterQualityStatus = async () => {
  try {
    const response = await fetch(`${API_URL}/water-quality/`)
    if (!response.ok) {
      throw new Error('Failed to fetch water quality status')
    }
    return await response.json()
  } catch (error) {
    console.error('Error fetching water quality status:', error)
    throw error
  }
}
