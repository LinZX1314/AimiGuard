import { createRouter, createWebHashHistory } from 'vue-router'
import Layout from '../components/Layout.vue'
import DefenseDashboard from '../views/DefenseDashboard.vue'
import ScanManager from '../views/ScanManager.vue'
import AICenter from '../views/AICenter.vue'
import Login from '../views/Login.vue'
import DefenseRealtime from '../views/DefenseRealtime.vue'
import ProbeRealtime from '../views/ProbeRealtime.vue'
import SettingsPage from '../views/SettingsPage.vue'
import ProfilePage from '../views/ProfilePage.vue'
import OverviewPage from '../views/OverviewPage.vue'
import ProbeDashboardPage from '../views/ProbeDashboardPage.vue'
import IntegrationsPage from '../views/IntegrationsPage.vue'
import AuditPage from '../views/AuditPage.vue'
import ObservabilityPage from '../views/ObservabilityPage.vue'
import ForbiddenPage from '../views/ForbiddenPage.vue'
import WorkflowCatalogPage from '../views/WorkflowCatalogPage.vue'
import WorkflowRunsPage from '../views/WorkflowRunsPage.vue'
import WorkflowReadonlyGraphPage from '../views/WorkflowReadonlyGraphPage.vue'
import WorkflowEditorPage from '../views/WorkflowEditorPage.vue'
import { hasAnyPermission, parseStoredUserInfo } from '../composables/useAuthz'

type UserRole = 'admin' | 'operator' | 'viewer'

const allowedRolesMap: Record<UserRole, UserRole[]> = {
  admin: ['admin', 'operator', 'viewer'],
  operator: ['operator', 'viewer'],
  viewer: ['viewer'],
}

const hasRoleAccess = (requiredRoles?: UserRole[]): boolean => {
  if (!requiredRoles || requiredRoles.length === 0) return true
  const user = parseStoredUserInfo()
  const role = (user?.role || 'viewer') as UserRole
  const granted = allowedRolesMap[role] || ['viewer']
  return requiredRoles.some((required) => granted.includes(required))
}

const hasPermissionAccess = (requiredPermissions?: string[]): boolean => {
  if (!requiredPermissions || requiredPermissions.length === 0) return true
  return hasAnyPermission(requiredPermissions)
}

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: Login,
      meta: { requiresAuth: false }
    },
    {
      path: '/forbidden',
      name: 'forbidden',
      component: ForbiddenPage,
      meta: { requiresAuth: true }
    },
    {
      path: '/',
      component: Layout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/defense/dashboard'
        },
        {
          path: '/defense/dashboard',
          name: 'defense-dashboard',
          component: OverviewPage
        },
        {
          path: '/probe/dashboard',
          name: 'probe-dashboard',
          component: ProbeDashboardPage
        },
        {
          path: '/overview',
          redirect: '/defense/dashboard'
        },
        {
          path: '/defense/realtime',
          name: 'defense-realtime',
          component: DefenseRealtime
        },
        {
          path: '/defense/events',
          name: 'defense-events',
          component: DefenseDashboard
        },
        {
          path: '/defense/ai',
          name: 'defense-ai',
          component: AICenter
        },
        {
          path: '/probe/realtime',
          name: 'probe-realtime',
          component: ProbeRealtime
        },
        {
          path: '/probe/scan',
          name: 'probe-scan',
          component: ScanManager
        },
        {
          path: '/probe/ai',
          name: 'probe-ai',
          component: AICenter
        },
        {
          path: '/settings',
          name: 'settings',
          component: SettingsPage
        },
        {
          path: '/integrations',
          name: 'integrations',
          component: IntegrationsPage,
          meta: { requiredRoles: ['operator', 'admin'] }
        },
        {
          path: '/audit',
          name: 'audit',
          component: AuditPage,
          meta: { requiredRoles: ['operator', 'admin'] }
        },
        {
          path: '/workflow/catalog',
          name: 'workflow-catalog',
          component: WorkflowCatalogPage,
          meta: { requiredPermissions: ['workflow_view'] }
        },
        {
          path: '/workflow/runs',
          name: 'workflow-runs',
          component: WorkflowRunsPage,
          meta: { requiredPermissions: ['workflow_view'] }
        },
        {
          path: '/workflow/:id/graph',
          name: 'workflow-readonly-graph',
          component: WorkflowReadonlyGraphPage,
          meta: { requiredPermissions: ['workflow_view'] }
        },
        {
          path: '/workflow/new',
          name: 'workflow-editor-new',
          component: WorkflowEditorPage,
          meta: { requiredPermissions: ['workflow_edit'] }
        },
        {
          path: '/workflow/:id/edit',
          name: 'workflow-editor',
          component: WorkflowEditorPage,
          meta: { requiredPermissions: ['workflow_edit'] }
        },
        {
          path: '/observability',
          name: 'observability',
          component: ObservabilityPage,
          meta: { requiredRoles: ['admin'] }
        },
        {
          path: '/profile',
          name: 'profile',
          component: ProfilePage
        },
        {
          path: '/defense',
          redirect: '/defense/dashboard'
        },
        {
          path: '/scan',
          redirect: '/probe/scan'
        },
        {
          path: '/ai',
          redirect: '/defense/ai'
        },
        {
          path: '/ai-center',
          redirect: '/defense/ai'
        },
        {
          path: '/workflow',
          redirect: '/workflow/catalog'
        }
      ]
    }
  ]
})

// Route guard
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')

  if (to.meta.requiresAuth !== false && !token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  } else if (to.path === '/login' && token) {
    next('/')
    return
  }

  const requiredRoles = to.meta.requiredRoles as UserRole[] | undefined
  const requiredPermissions = to.meta.requiredPermissions as string[] | undefined
  if (to.meta.requiresAuth !== false && (!hasRoleAccess(requiredRoles) || !hasPermissionAccess(requiredPermissions))) {
    next('/forbidden')
    return
  }

  if (to.matched.length === 0) {
    next('/defense/dashboard')
  } else {
    next()
  }
})

export default router
