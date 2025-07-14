<script lang="ts">
    // @ts-nocheck
    import { onMount, getContext } from 'svelte';
    import { toast } from 'svelte-sonner';
    import { dirHandle } from '$lib/stores';

    const i18n = getContext('i18n');

    let customFilename = '';
    export let saveHandler: Function;

    const setFilePath = async () => {
    try {
        const handle = await window.showDirectoryPicker();
        dirHandle.set(handle);

        toast.success('File path set');
        console.log('Chosen file handle:', handle);
        saveExportHandle(handle);
    } catch (err) {
        if (err.name !== 'AbortError') {
            console.error('Failed to pick save path:', err);
            toast.error('Failed to set file path');
        }
    }
    };



    export async function saveExportHandle(handle) {
    const db = await new Promise((resolve, reject) => {
        const request = indexedDB.open(dbName, 2);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });

    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    store.put({ id: 'exportDir', handle });
    await new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => reject(tx.error);
    });
    db.close();
}

const dbName = 'pathStore';
const storeName = 'filepath';

onMount(async () => {
    let statusMessage = 'Checking for existing export location...';

    try {
        const dbRequest = indexedDB.open(dbName, 2);

        dbRequest.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(storeName)) {
                db.createObjectStore(storeName, { keyPath: 'id' });
            }
        };

        const db = await new Promise((resolve, reject) => {
            dbRequest.onsuccess = () => resolve(dbRequest.result);
            dbRequest.onerror = () => reject(dbRequest.error);
        });

        const tx = db.transaction(storeName, 'readonly');
        const store = tx.objectStore(storeName);
        const getRequest = store.get('exportDir');

        const result = await new Promise((resolve, reject) => {
            getRequest.onsuccess = () => resolve(getRequest.result);
            getRequest.onerror = () => reject(getRequest.error);
        });

        const storedHandle = result?.handle;

        if (storedHandle) {
            const permissionStatus = await storedHandle.queryPermission({ mode: 'readwrite' });

            if (permissionStatus === 'granted') {
                dirHandle.set(storedHandle);
                statusMessage = `Current export location: ${storedHandle.name}`;
            } else if (permissionStatus === 'prompt') {
                const requestResult = await storedHandle.requestPermission({ mode: 'readwrite' });
                if (requestResult === 'granted') {
                    dirHandle.set(storedHandle);
                    statusMessage = `Current export location: ${storedHandle.name}`;
                } else {
                    await clearExportHandle(db);
                    dirHandle.set(null);
                    statusMessage = 'Permission denied for previous location. Please set a new one.';
                    toast.warning(statusMessage);
                }
            } else {
                await clearExportHandle(db);
                dirHandle.set(null);
                statusMessage = 'Permission denied for previous location. Please set a new one.';
                toast.warning(statusMessage);
            }
        } else {
            statusMessage = 'No export location set. Click to choose.';
        }

        db.close();
    } catch (err) {
        console.error('Error during onMount:', err);
        statusMessage = 'Error loading export location. Please set one.';
        toast.error(statusMessage);
        dirHandle.set(null);
    }
});

</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={async () => {
		saveHandler();
	}}
>   
	<div class="self-center text-s font-medium">
		{`Save Directory: ${$dirHandle?.name || 'No export location set'}`}
	</div>

	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="text-xs px-3 py-1.5 bg-gray-50 hover:bg-gray-100 dark:bg-gray-850 dark:hover:bg-gray-800 transition rounded-lg font-medium"
			type="button"
			on:click={setFilePath}
		>
			{$i18n?.t('Set export location') || 'Set Export Location'}
		</button>
	</div>
</form>
