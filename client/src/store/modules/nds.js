import { defineStore } from 'pinia';
import { GetNDSList, AddNDSItem, UpdateNDSItem, DeleteNDSItem } from "@/apis/mparser/NDS";

export const useNDSStore = defineStore('nds', {
  state: () => ({
    ndsList: [],
    loading: false,
    searchKeyword: ''
  }),

  getters: {
    displayedNodes: (state) => {
      if (!state.searchKeyword) return state.ndsList;
      const query = state.searchKeyword.toLowerCase();
      return state.ndsList.filter(item => 
        item.NDSName.toLowerCase().includes(query) ||
        item.Address.toLowerCase().includes(query) ||
        item.Protocol.toLowerCase().includes(query)
      );
    }
  },

  actions: {
    async fetchList() {
      this.loading = true;
      try {
        const result = await GetNDSList();
        this.ndsList = result.list.map(item => ({
          ...item,
          id: item.ID,
          status: 'offline',
          icon: 'AiFillDatabase',
          loading: false,
          state: ''
        }));
      } finally {
        this.loading = false;
      }
    },

    async updateNode(data) {
      const node = this.ndsList.find(item => item.ID === data.ID);
      if (!node) return false;

      node.loading = true;
      try {
        const result = await UpdateNDSItem(data);
        if (result.success) {
          const index = this.ndsList.findIndex(item => item.ID === data.ID);
          if (index !== -1) {
            this.ndsList[index] = {
              ...result.data,
              id: result.data.ID,
              status: 'offline',
              icon: 'AiFillDatabase',
              loading: false,
              state: ''
            };
          }
          return true;
        }
        return false;
      } finally {
        node.loading = false;
      }
    }
  }
}); 