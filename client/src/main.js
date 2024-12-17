import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css' //夜间模式主题
import zhCn from 'element-plus/es/locale/lang/zh-cn' //中文语言包
import { createPinia } from 'pinia';
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';
import router from "@/router";

const pinia = createPinia();
pinia.use(piniaPluginPersistedstate);

const app = createApp(App);
app
    .use(router)
    .use(ElementPlus, {locale: zhCn})
    .use(pinia)
    .mount('#app');
