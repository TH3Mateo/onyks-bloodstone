<script setup lang="js">
    import { ref } from 'vue'
    import { defineModel } from 'vue'
    import { defineExpose } from 'vue'
    

    const props = defineProps(['action', 'subject'])
    const emit = defineEmits(['add-click', 'edit-click', 'delete-click'])

    const name = defineModel('name')
    const id = defineModel('id')

    const btns = ref({add: null, edit: null, delete: null})
    const values = ref([])
    const total = ref(0)
    const counter = ref(0)
    
    const reset = async () =>
    {
        props.action(100, 0).then((e) => 
        {
            values.value = e.data.items
            total.value = e.data.total
            counter.value = values.value.length
        })
        name.value = ''
        try
        {
            changeValue({detail:{selected: false}})
        }
        catch(error)
        {}
    }

    const refresh = async () =>
    {
        props.action(100, counter.value).then((e) => 
        {
            values.value = [...values.value, ...e.data.items]
            counter.value = values.value.length
            total.value = e.data.total
        })
    }

    const changeValue = (e) =>
    {
        if(e.detail.selected)
        {
            name.value = e.detail.value[1]
            id.value = e.detail.value[0]
            btns.value.delete.disabled = false
            btns.value.edit.disabled = false
        }
        else
        {
            name.value = ''
            id.value = 0
            btns.value.edit.disabled = true
            btns.value.delete.disabled = true
        }
    }

    defineExpose(
    {
        reset,
        name,
        id
    })

    reset()


</script>

<template>
    <onyks-container type="stack" padding="" gap="l">
        
        <onyks-select ref="select" @scroll-end="refresh" @change="changeValue">
            <onyks-select-option v-for="value in values" :key="value" :value="[value.id, value.name]">{{ value.name }}</onyks-select-option>
        </onyks-select>

        <onyks-text>Total:&emsp;{{counter}}&emsp;/&emsp;{{ total }}</onyks-text>


        <onyks-container type="grid" cols="3" padding="" gap="m">
            <onyks-button background="green" @click="emit('add-click')">Add</onyks-button>
            <onyks-button background="blue" @click="emit('edit-click')" :ref="(el) => { if (el) btns.edit = el }" disabled>Edit</onyks-button>
            <onyks-button @click="emit('delete-click')" :ref="(el) => { if (el) btns.delete = el }" disabled>Delete</onyks-button>
        </onyks-container>
    </onyks-container>
</template>

<style lang="css" scoped>
    onyks-button
    {
        width: 100%;
    }

    onyks-select
    {
        width: 100%;
        height: 160px;
    }
</style>