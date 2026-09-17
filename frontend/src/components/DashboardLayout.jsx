import Sidebar from './Sidebar'

const DashboardLayout = ({ children }) => {
    return (
        <div className="flex h-screen modern-bg">
            <Sidebar />
            <main className="flex-1 overflow-y-auto ml-4 mr-4 mb-4 rounded-2xl">
                {children}
            </main>
        </div>
    )
}

export default DashboardLayout
