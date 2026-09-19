<script setup>
    import { ref, onMounted } from 'vue';
    import { settings } from '@/utils/api.js';

    const identity = ref({
        svnRepository: '',
        databaseHost: '',
        databasePort: '',
        databaseName: '',
        altiumDatabase: '',
        kicadDatabase: ''
    })

    onMounted(async () =>
    {
        const res = await settings.identity()
        if (res.status == 200)
        {
            identity.value = res.data
        }
    })
</script>

<template>
    <onyks-container gap="l" padding="l">

        <onyks-header>Settings</onyks-header>

        <onyks-container gap="l" type="grid" cols="2" padding="">

            <onyks-card title="Connection Info" size="l">
                <onyks-container gap="m" padding="">
                    <onyks-text size="s">
                        Use these details to configure an ODBC Data Source (required by both Altium and KiCad
                        database libraries). Sign in with the same login and password you use for this
                        application and for SVN — it is one account. Your account only grants read access,
                        and only to the tables belonging to your CAD tool. Point the data source at your
                        tool's database below — it contains nothing but the component categories.
                    </onyks-text>

                    <onyks-container type="group" align="center" padding="" cols="2">
                        <onyks-header level="6">Database host:</onyks-header>
                        <onyks-text>{{ identity.databaseHost || 'Undefined' }}</onyks-text>
                    </onyks-container>
                    <onyks-container type="group" align="center" padding="" cols="2">
                        <onyks-header level="6">Database port:</onyks-header>
                        <onyks-text>{{ identity.databasePort || 'Undefined' }}</onyks-text>
                    </onyks-container>
                    <onyks-container type="group" align="center" padding="" cols="2">
                        <onyks-header level="6">Database (Altium):</onyks-header>
                        <onyks-text>{{ identity.altiumDatabase || 'Undefined' }}</onyks-text>
                    </onyks-container>
                    <onyks-container type="group" align="center" padding="" cols="2">
                        <onyks-header level="6">Database (KiCad):</onyks-header>
                        <onyks-text>{{ identity.kicadDatabase || 'Undefined' }}</onyks-text>
                    </onyks-container>
                    <onyks-container type="group" align="center" padding="" cols="2">
                        <onyks-header level="6">SVN repository:</onyks-header>
                        <onyks-text>{{ identity.svnRepository || 'Undefined' }}</onyks-text>
                    </onyks-container>
                    <onyks-container type="group" align="center" padding="" cols="2">
                        <onyks-header level="6">Username:</onyks-header>
                        <onyks-text>your own account</onyks-text>
                    </onyks-container>
                </onyks-container>
            </onyks-card>

            <onyks-card title="Download Library Files" size="l">
                <onyks-container gap="m" padding="">
                    <onyks-text size="s">
                        Both files are generated fresh from the current database every time you download them —
                        any new category table is reflected automatically. Username and password are left blank;
                        sign in with your own account. Altium and KiCad each connect to their own database and
                        cannot see the other's tables.
                    </onyks-text>

                    <onyks-button background="blue" @click="settings.downloadDbLib">Download Altium .DbLib</onyks-button>
                    <onyks-button background="green" @click="settings.downloadKicadDbl">Download KiCad .kicad_dbl</onyks-button>

                    <onyks-text size="s">
                        For KiCad: register each SchLib/PcbLib file in your Symbol/Footprint Library Table with
                        Type = Altium, using the file name (without extension) as the library nickname — this
                        must match the "Symbols"/"Footprints" columns generated in the database views.
                    </onyks-text>
                </onyks-container>
            </onyks-card>

        </onyks-container>

    </onyks-container>
</template>

<style scoped>
    onyks-button
    {
        width: 100%;
    }
</style>
