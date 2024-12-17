// noinspection JSUnresolvedReference

import { ref } from 'vue';
import { defineStore } from 'pinia';


const tabStore = defineStore('tabs', {
    state: () => ({
        homeTab: {
            name: '首页',
            path: '/home',
            icon: 'BiHome',
            component: 'Home'
        },
        pathFilter: ['/', '/home', '/login'],
        openTab: [],
        activeIndex: ''
    }),
    actions: {
        init() {
            if (this.openTab.length === 0) {
                this.openTab = [this.homeTab]
            }

            const currentPath = window.location.pathname

            const existingTab = this.openTab.find(tab => tab.path === currentPath)
            if (existingTab) {
                this.setActiveIndex(currentPath)
            }
        },
        addTabs(data) {
            // 在 userRoutes 中查找对应路径的组件名称
            const findComponentByPath = (path, routes) => {
                for (const route of routes) {
                    if (route.path === path) {
                        return route.component;
                    }
                    if (route.children) {
                        const found = findComponentByPath(path, route.children);
                        if (found) return found;
                    }
                }
                return null;
            };

            if (data.name === 'NotFound'){
                const index = this.openTab.findIndex(option => option.name === data.name)
                if (index !== -1) {
                    this.openTab[index] = {
                        ...this.openTab[index],
                        path: data.path,
                        icon: data.icon || 'BiHome',
                        component: findComponentByPath(data.path, userRoutes.value) || data.name
                    }
                    this.activeIndex = this.openTab[index].path
                    return
                }
            }

            const tabData = {
                ...data,
                icon: data.icon || '',
                component: findComponentByPath(data.path, userRoutes.value) || data.name
            }
            this.openTab.push(tabData)
        },
        setActiveIndex(index) {
            this.activeIndex = index
        },
        deleteTabs(path) {
            const index = this.openTab.findIndex(option => option.path === path)
            if (index !== -1) {
                this.openTab.splice(index, 1)
            }
        },
        reorderTabs(fromIndex, toIndex) {
            console.log(fromIndex, toIndex)
            const tabToMove = this.openTab[fromIndex]

            this.openTab.splice(fromIndex, 1)

            this.openTab.splice(toIndex, 0, tabToMove)

            this.openTab = [...this.openTab]
        }
    },
    persist: {
        storage: window.sessionStorage
    }
})

const userInfoStore = defineStore('userInfo', {
    state: () => ({
        userInfo: null,
    }),
    actions: {
        setUserInfo(userInfo) {
            this.userInfo = userInfo;
        },
        clearUserInfo() {
            this.userInfo = null;
        },
    },
    persist: {
        storage: window.sessionStorage
    },
});

import {useDark, useToggle} from "@vueuse/core";
const themeStore = defineStore('theme', {
    state: () => ({
        isDark: useDark(),
    }),
    actions: {
        initTheme() {
            const darkItem = 'light'; // 默认为 'light'
            const dark = darkItem === 'dark';
            if (dark !== this.isDark.value) { useToggle(); }
        },
        toggleTheme() {
            return useToggle();
        }
    },
    persist: {
        storage: window.localStorage
    },
});

const collapseStore = defineStore('collapse', {
    state: () => ({
        isCollapse: false,
    }),
    actions: {
        toggleCollapse() {
            this.isCollapse = !this.isCollapse;
        }
    },
    persist: {
        storage: window.localStorage
    },
});

const isLogin = ref(false);

const userRoutes = ref([]);

const UserProfileActiveTab = ref("info");



export { tabStore, userInfoStore, themeStore, collapseStore, isLogin, userRoutes, UserProfileActiveTab };

