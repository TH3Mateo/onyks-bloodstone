<script setup>
    import { useWindowSize } from '@vueuse/core'

    const props = defineProps(['names'])
    const model = defineModel() // null = all categories selected, array = explicit subset
    const { width } = useWindowSize()

    const isChecked = (name) => model.value === null || model.value.includes(name)

    const toggle = (name) =>
    {
        let current = model.value === null ? [...props.names] : [...model.value]
        const index = current.indexOf(name)
        if (index === -1)
        {
            current.push(name)
        }
        else
        {
            current.splice(index, 1)
        }
        model.value = current.length === props.names.length ? null : current
    }

    const selectAll = () => { model.value = null }
    const selectNone = () => { model.value = [] }
</script>

<template>
    <onyks-container gap="s" padding="">
        <onyks-container type="group" align="center" padding="" gap="s">
            <onyks-button size="s" background="blue" @click="selectAll">Select all</onyks-button>
            <onyks-button size="s" @click="selectNone">Deselect all</onyks-button>
        </onyks-container>

        <onyks-container type="grid" :cols="width > 1100 ? 4 : width > 700 ? 3 : 2" padding="" gap="s">
            <onyks-container v-for="name in props.names" :key="name" padding="" gap="s" type="group" align="center">
                <onyks-checkbox
                    :checked="isChecked(name)"
                    size="s"
                    @change="() => toggle(name)">
                </onyks-checkbox>
                <onyks-text size="s">{{ name }}</onyks-text>
            </onyks-container>
        </onyks-container>
    </onyks-container>
</template>

<style scoped>
    onyks-button
    {
        width: fit-content;
    }
</style>
