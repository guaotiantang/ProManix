// noinspection JSUnresolvedReference,JSUnusedLocalSymbols
// 使用 /* @vite-ignore */ 注释来忽略动态导入警告

import { createRouter, createWebHistory } from 'vue-router';
import NProgress from 'nprogress';
import 'nprogress/nprogress.css';

// 路由映射配置
const routeMap = [
    {name: "Redirect", path: "../components/framework/Redirect.vue"},
    {name: "Home", path: "../views/default/home.vue"},
    {name: "404Page", path: "../views/default/404.vue"},
    {name: "UserProfile", path: "../views/default/UserProfile.vue"},
    {name: "Role", path: "../views/default/Role.vue"},
    {name: "Tasks", path: "../views/mparser/Tasks.vue"},
    {name: "NDSManage", path: "../views/mparser/NDSManage.vue"},
    {name: "CellData", path: "../views/mparser/CellData.vue"},
];

// 使用 @vite-ignore 注释来处理动态导入
const components = {};
for (const route of routeMap) {
    components[route.name] = () => /* @vite-ignore */ import( /* @vite-ignore */ route.path);
}

// 路由配置
const routesConfig = [
    {
        name: '/', // 定义 /home 路由
        path: '/',
        component: 'Home',
        redirect: '/home',
        meta: {
            hidden: true,
            icon: 'BiHome',
        },
    },
    {
        name: '首页', // 定义 /home 路由
        path: '/home',
        component: 'Home',
        meta: {
            hidden: false,
            icon: 'BiHome',
        },
    },
    {
        name: 'Login',
        path: '/login',
        component: 'Home',
        redirect: '/home',
        meta: {
            hidden: true,
            icon: 'BsListTask',
        },
    },
    {
        // 404 page
        name: 'NotFound',
        path: '/:pathMatch(.*)*',
        component: '404Page',
        meta: {
            hidden: true,
            icon: 'BsListTask',
        },

    },
    {
        name: '系统管理',
        path: '/sys',
        meta: {
            hidden: false,
            icon: 'EpSetting',
        },
        redirect: '/sys/profile',
        children: [
            {
                name: '个人信息',
                path: '/sys/profile',
                component: 'UserProfile',
                meta: {
                    hidden: false,
                    icon: 'BsPerson',
                },
            },
            {
                name: '角色管理',
                path: '/sys/role',
                component: 'Role',
                meta: {
                    hidden: false,
                    icon: 'BsPeople',
                },
            },

        ],
    },
    {
        name: 'MParser',
        path: '/mparser',
        meta: {
            hidden: false,
            icon: 'GrSystem',
        },
        children: [
            {
                name: '任务管理',
                path: '/mparser/tasks',
                component: 'Tasks',
                meta: {
                    hidden: false,
                    icon: 'RiPlayList2Fill',
                },
            },
            {
                name: 'CellData',
                path: '/mparser/cellData',
                component: 'CellData',
                meta: {
                    hidden: false,
                    icon: 'BiSpreadsheet',
                },
            },
            {
                name: 'NDS管理',
                path: '/mparser/nds',
                component: 'NDSManage',
                meta: {
                    hidden: false,
                    icon: 'AiFillDatabase',
                },
            },
        ],
    },
    {
        name: '关于',
        path: '/about',
        component: 'About',
        meta: {
            hidden: false,
            icon: 'BsInfoCircle',
        },
    },
    {
        path: '/redirect/:path(.*)', // 重定向到指定路径
        component: 'Redirect', // 使用 Redirect 组件,
    }

];

import { userRoutes } from '@/store';
userRoutes.value = routesConfig;

// 递归处理路由配置，包括子路由
const processRoutes = (routes) => {
    return routes.map(route => {
        const processedRoute = {
            ...route,
            component: components[route.component],
        };
        
        if (route.children) {
            processedRoute.children = processRoutes(route.children);
        }
        
        return processedRoute;
    });
};

// 使用递归函数处理所有路由
const routes = processRoutes(routesConfig);

// 处理路由的 children 属性，将其转换为实际的组件
const topLevelRoutes = routes.filter(route => {const { children, ...rest} = route; return rest});
const topLevelNames = new Set(topLevelRoutes.map(route => route.name));
const router = createRouter({
    history: createWebHistory('/'),
    routes: topLevelRoutes,
});

// 设置 NProgress 配置项（可选）
NProgress.configure({ showSpinner: false }); // 关闭右上角的加载旋转器

// 使用全局前置守卫启动 NProgress
router.beforeEach((to, from, next) => {
    NProgress.start();
    next();
});

// 使用全局后置钩子结束 NProgress
router.afterEach(() => {
    NProgress.done();
});

router.getRoutes().forEach(route => {
    if (route.name && !topLevelNames.has(route.name)) {
        route.meta['hidden'] = true;
    }
})

export default router;
