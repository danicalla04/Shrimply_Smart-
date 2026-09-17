import { initializeApp } from 'firebase/app'
import { getDatabase, ref, onValue } from 'firebase/database'

// Read config from Vite env vars
const firebaseConfig = {
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    databaseURL: import.meta.env.VITE_FIREBASE_DB_URL,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
}

let app = null
let db = null

export function initFirebase() {
    if (!firebaseConfig.databaseURL) return false
    if (!app) {
        try {
            app = initializeApp(firebaseConfig)
            db = getDatabase(app)
        } catch (e) {
            console.warn('Firebase init failed', e)
            return false
        }
    }
    return true
}

// Listen to /sensors/latest and call callback with plain JS object when value changes
export function listenLatestSensors(callback) {
    if (!initFirebase()) return () => { }
    const r = ref(db, '/sensors/latest')
    const unsubscribe = onValue(r, (snapshot) => {
        const val = snapshot.val()
        callback(val)
    }, (err) => {
        console.warn('Firebase onValue error', err)
    })
    return unsubscribe
}

export default { initFirebase, listenLatestSensors }
