import { ref } from 'vue'

import { getProjects } from '@/api/configuration'

export function useRequirementProjects() {
  const projects = ref([])
  const selectedProject = ref()

  async function loadProjects() {
    const { data } = await getProjects({ status: 'active', page_size: 100 })
    projects.value = Array.isArray(data) ? data : data.results || []
    selectedProject.value = projects.value.find(project => project.is_default)?.id || projects.value[0]?.id
  }

  return {
    projects,
    selectedProject,
    loadProjects,
  }
}
